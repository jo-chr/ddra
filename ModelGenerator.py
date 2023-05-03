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
        self. resources = list(state_log["resource"].unique())

        logging.basicConfig(level=logging_level)



    def generate_model(self):
        
        spn = SPN()
        
        print('Discover material flow model')
        net, im, fm = pm4py.discover_petri_net_alpha(self.event_log, activity_key='event', case_id_key='order_id', timestamp_key='timestamp')

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
                transition.distribution = self._estimate_arrival_time_distribution(time_unit="s", export_plots=False)

        #----determine & parameterize resource timed transtions----#
        print('Determine resource transitions & fit distributions')

        for resource in self.resources:
            resource_dist = self._estimate_resource_activtiy_distribtuion(resource)
            spn.get_transition_by_label(resource)
            


        return spn
    
   
    def _estimate_arrival_time_distribution(self, time_unit = "s", export_plots = True):

        arrival_times = list(self.event_log[self.event_log["event"]=="new_order"]["timestamp"])
        match time_unit:
            case "s":
                arrival_times_td =[(x-y).seconds for x, y in zip(arrival_times[1:], arrival_times)]
            case "m":
                arrival_times_td =[((x-y).seconds//60)%60 for x, y in zip(arrival_times[1:], arrival_times)]
            case "h":
                arrival_times_td =[(x-y).seconds//3600 for x, y in zip(arrival_times[1:], arrival_times)]
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
        
        return f.get_best()
    
    def _estimate_resource_activtiy_distribtuion(self, resource, time_unit = "s", export_plots = True):

        busy_times = []
        idle_times = []
        activity_durations = []

        resource_state_log = self.state_log[self.state_log["resource"]==resource]
        busy_times = resource_state_log[resource_state_log["state"]=="busy"]["timestamp"]
        idle_times = resource_state_log[resource_state_log["state"]=="idle"]["timestamp"]

        match time_unit:
            case "s":
                activity_durations = [(x-y).seconds for x,y in zip(idle_times,busy_times)]
            case "m":
                activity_durations = [((x-y).seconds//60)%60 for x,y in zip(idle_times,busy_times)]
            case "h":
                activity_durations = [(x-y).seconds//3600 for x,y in zip(idle_times,busy_times)]
            case "d":
                activity_durations = [(x-y).days for x,y in zip(idle_times,busy_times)]
            case _:
                raise Exception("time_unit undefined: {}.".format(time_unit))    
    
        f = Fitter(activity_durations,distributions=get_common_distributions())
        f.fit()

        if export_plots == True:
            f.hist()
            f.plot_pdf(Nbest=1)
            plt.title("Fitted resource activity distribution " + str(resource))
            plt.xlabel(time_unit)
            plt.savefig(distributions_dir + str(resource) + "_activity_dist.png")

        return f.get_best()



        