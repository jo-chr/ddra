import sys
sys.path.append('../')

try:
    from ..spn_simulator.components.spn import *
    from ..spn_simulator.components.spn_visualization import *
    from ..spn_simulator.components.spn_simulate import *
    from ..spn_simulator.components.spn_io import *
except:
    from spn_simulator.components.spn import *
    from spn_simulator.components.spn_visualization import *
    from spn_simulator.components.spn_simulate import *
    from spn_simulator.components.spn_io import *

import logging
import pm4py
import re
from fitter import Fitter, get_common_distributions
import matplotlib.pyplot as plt


distributions_dir = "output/distributions/"


class ModelGenerator:
    
    def __init__(self, event_log, state_log, logging_level=logging.CRITICAL):
        self.event_log = event_log
        self.state_log = state_log
        self.activities = list(event_log["event"][event_log["event_type"].notnull()].unique())
        self. resources = list(state_log["resource"].unique())


        logging.basicConfig(level=logging_level)



    def generate_model(self):
        
        spn = SPN()
        
        print('Discover material flow model')
        net, im, fm = pm4py.discover_petri_net_alpha(self.event_log[self.event_log["event_type"]!="end"], activity_key='event', case_id_key='order_id', timestamp_key='timestamp')

        #add places from pm4py pn to custom SPN
        for place in net.places:
            if "start" not in str(place) and "end" not in str(place):
                new_place = Place(label=str(place), n_tokens=0)
                spn.add_place(new_place)

        #add transitions from pm4py pn to custom SPN
        transition:Transition
        for transition in net.transitions:
            new_transition = Transition(label=str(transition),t_type="I")
            spn.add_transition(new_transition)
        
        #add arcs from pm4py pn to custom SPN
        for arc in net.arcs:
            if "start" not in str(arc) and "end" not in str(arc):
                for transition in spn.transitions:
                    if str(arc.source) == transition.label:
                        spn.add_output_arc(transition,spn.get_place_by_label(str(arc.target)))
                    if str(arc.target) == transition.label:
                        spn.add_input_arc(spn.get_place_by_label(str(arc.source)),transition)

        #rename transitions in custom SPN
        for transition in spn.transitions:
            transition.label = re.sub(r'[^\w,]', '',transition.label.split(",")[0])
        
        #rename palces in custom SPN
        for place in spn.places:
            place.label = re.sub(r'[^\w,]', '', place.label)

        #----determine & parameterize arrival time timed transitions----#
        print('Determine arrival transitions & fit distributions')

        for transition in spn.transitions:
            if transition.input_arcs == []:
                transition.t_type = "T"
                transition.time_unit = "s"
                transition.distribution = self._estimate_arrival_time_distribution(time_unit="s", export_plots=True)

        #----determine & parameterize timed transtions----#
        print('Determine timed transitions & fit distributions')

        for activity in self.activities:
            activity_dist = self._estimate_activity_distribution(activity)
            for transition in spn.transitions:
                if transition.label == activity:
                    transition.t_type = "T"
                    transition.time_unit = "s"
                    transition.distribution = activity_dist

        #----create resource failure models----#
        print('Create resource failure models & fit failure and repair distributions')

        for resource in self.resources:
            self._create_resource_failure_model(resource, spn)

        return spn
    
   
    def _estimate_arrival_time_distribution(self, time_unit = "s", export_plots = True):

        arrival_times = list(self.event_log[self.event_log["event"]=="new_order"]["timestamp"])
        match time_unit:
            case "s":
                arrival_times_td =[(x-y).total_seconds() for x, y in zip(arrival_times[1:], arrival_times)] #.seconds
            case "m":
                arrival_times_td =[((x-y).total_seconds()//60)%60 for x, y in zip(arrival_times[1:], arrival_times)]
            case "h":
                arrival_times_td =[(x-y).total_seconds()//3600 for x, y in zip(arrival_times[1:], arrival_times)]
            case "d":
                arrival_times_td =[(x-y).days for x, y in zip(arrival_times[1:], arrival_times)]
            case _:
                raise Exception("time_unit undefined: {}.".format(time_unit))    

        f = Fitter(arrival_times_td,distributions=get_common_distributions())
        f.fit()

        if export_plots == True:
            f.hist()
            f.plot_pdf(Nbest=1)
            plt.title("Fitted arrival time distribution")
            plt.xlabel(time_unit)
            plt.savefig(distributions_dir + "arrival_time_dist.png")
            plt.clf()
        
        return f.get_best()
    
    def _estimate_activity_distribution(self, activity, time_unit = "s", export_plots = True):

        start_times = []
        end_times = []
        activity_durations = []

        activity_log = self.event_log[self.event_log["event"]==activity]
        start_times = activity_log[activity_log["event_type"]=="start"]["timestamp"]
        end_times = activity_log[activity_log["event_type"]=="end"]["timestamp"]

        match time_unit:
            case "s":
                activity_durations = [(x-y).total_seconds() for x,y in zip(end_times,start_times)]
            case "m":
                activity_durations = [((x-y).total_seconds()//60)%60 for x,y in zip(end_times,start_times)]
            case "h":
                activity_durations = [(x-y).total_seconds()//3600 for x,y in zip(end_times,start_times)]
            case "d":
                activity_durations = [(x-y).days for x,y in zip(end_times,start_times)]
            case _:
                raise Exception("time_unit undefined: {}.".format(time_unit))  
    
        f = Fitter(activity_durations,distributions=get_common_distributions()+ ["triang"])
        f.fit()

        if export_plots == True:
            f.hist()
            f.plot_pdf(Nbest=1)
            plt.title("Fitted activity distribution " + str(activity))
            plt.xlabel(time_unit)
            plt.savefig(distributions_dir + str(activity) + "_dist.png")
            plt.clf()

        return f.get_best()
    
    def _create_resource_failure_model(self, resource, spn):

        p_ok = Place(label="{}_OK".format(resource),n_tokens=1)
        p_failed = Place(label="{}_Failed".format(resource),n_tokens=0)

        t_fail = Transition(label="Fail_{}".format(resource), t_type="T")
        t_fail.distribution = self._estimate_resource_failure_model_distribution(resource, mode = "fail")

        t_repair = Transition(label="Repair_{}".format(resource), t_type="T")
        t_repair.distribution = self._estimate_resource_failure_model_distribution(resource, mode = "repair")

        spn.add_place(p_ok)
        spn.add_place(p_failed)

        spn.add_transition(t_fail)
        spn.add_transition(t_repair)

        spn.add_output_arc(t_repair,p_ok)
        spn.add_input_arc(p_ok,t_fail)
        spn.add_output_arc(t_fail,p_failed)
        spn.add_input_arc(p_failed,t_repair)

        for transition in spn.transitions:
            if resource == transition.label.split("_")[0]:
                spn.add_inhibitor_arc(transition=spn.get_transition_by_label(transition.label),place=p_failed)

    def _estimate_resource_failure_model_distribution(self, resource, mode, export_plots = True):

        failure_times = []
        repair_times = []
        durations = []

        resource_state_log = self.state_log[self.state_log["resource"]==resource]

        failure_times = resource_state_log[resource_state_log["state"]=="failure"]["timestamp"].tolist()
        repair_times = resource_state_log[resource_state_log["state"]=="repaired"]["timestamp"].tolist()

        if mode == "repair":
            durations = [(x-y).total_seconds() for x,y in zip(repair_times,failure_times)]

            f = Fitter(durations,distributions=get_common_distributions())
            f.fit()

            if export_plots == True:
                f.hist()
                f.plot_pdf(Nbest=1)
                plt.title("Fitted repair distribution " + str(resource))
                plt.xlabel("s")
                plt.savefig(distributions_dir + str(resource) + "repair_dist.png")
                plt.clf()

        if mode == "fail":
            
            failure_times.pop(0)
            durations = [(x-y).total_seconds() for x,y in zip(failure_times,repair_times)]

            f = Fitter(durations,distributions=get_common_distributions())
            f.fit()

            if export_plots == True:
                f.hist()
                f.plot_pdf(Nbest=1)
                plt.title("Fitted failure distribution " + str(resource))
                plt.xlabel("s")
                plt.savefig(distributions_dir + str(resource) + "failure_dist.png")
                plt.clf()

        return f.get_best()
