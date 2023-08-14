import numpy as np
import logging
import pm4py
import json
import re
from fitter import Fitter
import matplotlib.pyplot as plt

from pyspn.components import spn

distributions_dir = "output/distributions/"

class ModelExtractor:
    
    def __init__(self, event_log, state_log, config, logging_level=logging.CRITICAL):
        self.event_log = event_log
        self.state_log = state_log
        self.config = config
        self.activities = list(event_log["event"][event_log["event_type"].notnull()].unique())
        self.resources = list(state_log["resource"].unique())
        #logging.basicConfig(level=logging_level)

    def extract_model(self):
        
        rel_model = spn.SPN()
        
        print('Discover material flow model')
        net, im, fm = pm4py.discover_petri_net_alpha(self.event_log[self.event_log["event_type"]!="end"], activity_key='event', case_id_key='order_id', timestamp_key='timestamp')

        #add places from pm4py pn to custom SPN
        for place in net.places:
            if "start" not in str(place) and "end" not in str(place):
                new_place = spn.Place(label=str(place), n_tokens=0)
                rel_model.add_place(new_place)

        #add transitions from pm4py pn to custom SPN
        for transition in net.transitions:
            new_transition = spn.Transition(label=str(transition),t_type="I")
            rel_model.add_transition(new_transition)
        
        #add arcs from pm4py pn to custom SPN
        for arc in net.arcs:
            if "start" not in str(arc) and "end" not in str(arc):
                for transition in rel_model.transitions:
                    if str(arc.source) == transition.label:
                        rel_model.add_output_arc(transition,rel_model.get_place_by_label(str(arc.target)))
                    if str(arc.target) == transition.label:
                        rel_model.add_input_arc(rel_model.get_place_by_label(str(arc.source)),transition)

        #rename transitions in custom SPN
        for transition in rel_model.transitions:
            transition.label = re.sub(r'[^\w,]', '',transition.label.split(",")[0])
        
        #rename palces in custom SPN
        for place in rel_model.places:
            place.label = re.sub(r'[^\w,]', '', place.label)

        #----determine immediate transition firing weights----#
        print('Determine immediate transition firing weights')
        for transition in rel_model.transitions:
            if transition.t_type == "I":
                transition.weight = len(self.event_log[(self.event_log["event_type"]!="end") & (self.event_log["event"]==transition.label)])

        #----determine & parameterize arrival time timed transitions----#
        print('Determine arrival transitions & fit distributions')

        for transition in rel_model.transitions:
            if transition.input_arcs == []:
                transition.t_type = "T"
                transition.time_unit = self.config.get("TRANSITION_TIME_UNIT","time_unit")
                transition.distribution = self._estimate_arrival_time_distribution(time_unit=transition.time_unit, export_plots=True)

        #----determine & parameterize timed transtions----#
        print('Determine timed transitions & fit distributions')

        for activity in self.activities:
            activity_dist = self._estimate_activity_distribution(activity, time_unit=self.config.get("TRANSITION_TIME_UNIT","time_unit"), export_plots=True)
            for transition in rel_model.transitions:
                if transition.label == activity:
                    transition.t_type = "T"
                    transition.time_unit = self.config.get("TRANSITION_TIME_UNIT","time_unit")
                    transition.distribution = activity_dist

        #----determine capacities & add inhibitor arcs----#
        if self.config.getboolean("CAPACITY_EXTRACTION","extract_resource_capacities") == True:
            print('Determine resource capacities/buffer sizes & add inhibitor arcs to model')

            for capacaty_relation in self.config.items("CAPACITY_EXTRACTION.CAPACITY_RELATIONSHIPS"):
                current_cap = 0
                caps = []
                order_ids = []
                for order_id, event in zip(self.event_log[self.event_log["event_type"]!="end"]["order_id"],self.event_log[self.event_log["event_type"]!="end"]["event"]):
                    if capacaty_relation[0] in event:
                        current_cap +=1
                        caps.append(current_cap)
                        order_ids.append(order_id)
                    if capacaty_relation[1] in event and order_id in order_ids:
                        current_cap -=1

                for place in rel_model.places:
                        if place.label in "{},{}".format(capacaty_relation[0],capacaty_relation[1]):
                            transition_inhib = rel_model.get_transition_by_label(capacaty_relation[0])
                            rel_model.add_inhibitor_arc(transition_inhib,place,max(caps))

        #----create resource failure models----#
        print('Create resource failure models & fit failure and repair distributions')

        for resource in self.resources:
            self._create_resource_failure_model(resource, rel_model, time_unit=self.config.get("TRANSITION_TIME_UNIT","time_unit"))

        return rel_model
    
   
    def _estimate_arrival_time_distribution(self, time_unit, export_plots = True):

        arrival_times = list(self.event_log[self.event_log["event"]=="new_order"]["timestamp"])
        match time_unit:
            case "s":
                arrival_times_td =[(x-y).total_seconds() for x, y in zip(arrival_times[1:], arrival_times)] #.seconds
            case "m":
                arrival_times_td =[((x-y).total_seconds()/60)%60 for x, y in zip(arrival_times[1:], arrival_times)]
            case "h":
                arrival_times_td =[(x-y).total_seconds()//3600 for x, y in zip(arrival_times[1:], arrival_times)]
            case "d":
                arrival_times_td =[(x-y).days for x, y in zip(arrival_times[1:], arrival_times)]
            case _:
                raise Exception("time_unit undefined: {}.".format(time_unit))    

        f = Fitter(arrival_times_td,distributions=json.loads(self.config.get("DISTRIBUTIONS","dists")))
        f.fit()

        if export_plots == True:
            f.hist()
            f.plot_pdf(Nbest=1)
            plt.title("Fitted arrival time distribution")
            plt.xlabel(time_unit)
            plt.savefig(distributions_dir + "arrival_time_dist.pdf")
            plt.clf()
        
        return f.get_best()
    
    def _estimate_activity_distribution(self, activity, time_unit, export_plots = True):

        start_times = []
        end_times = []
        failure_times = []
        activity_durations = []

        activity_log = self.event_log[self.event_log["event"]==activity]
        failure_times = self.state_log[(self.state_log["resource"]==activity.split("_")[0]) & (self.state_log["state"]=="failure")]["timestamp"].reset_index(drop=True)
        start_times = activity_log[activity_log["event_type"]=="start"]["timestamp"].reset_index(drop=True)
        end_times = activity_log[activity_log["event_type"]=="end"]["timestamp"].reset_index(drop=True)

        #if failure timestamp is identical with "end" event_type time stamp -> remove whole start-end pair/exclude from dist fitting
        failure_times_matches=np.where(np.isin(end_times,failure_times))
        for index in sorted(list(failure_times_matches[0]), reverse=True):
            del start_times[index]
            del end_times[index]

        match time_unit:
            case "s":
                activity_durations = [(x-y).total_seconds() for x,y in zip(end_times,start_times)]
            case "m":
                activity_durations = [((x-y).total_seconds()/60)%60 for x,y in zip(end_times,start_times)]
            case "h":
                activity_durations = [(x-y).total_seconds()//3600 for x,y in zip(end_times,start_times)]
            case "d":
                activity_durations = [(x-y).days for x,y in zip(end_times,start_times)]
            case _:
                raise Exception("time_unit undefined: {}.".format(time_unit))  
    
        f = Fitter(activity_durations,distributions=json.loads(self.config.get("DISTRIBUTIONS","dists")))
        f.fit()

        if export_plots == True:
            f.hist()
            f.plot_pdf(Nbest=1)
            plt.title("Fitted activity distribution " + str(activity))
            plt.xlabel(time_unit)
            plt.savefig(distributions_dir + str(activity) + "_dist.pdf")
            plt.clf()

        return f.get_best()
    
    def _create_resource_failure_model(self, resource, rel_model, time_unit):

        p_ok = spn.Place(label="{}_ok".format(resource),n_tokens=1)
        p_failed = spn.Place(label="{}_failed".format(resource),n_tokens=0)

        t_fail = spn.Transition(label="fail_{}".format(resource), t_type="T")
        t_fail.distribution = self._estimate_resource_failure_model_distribution(resource, mode = "fail", time_unit=time_unit)

        t_repair = spn.Transition(label="repair_{}".format(resource), t_type="T")
        t_repair.distribution = self._estimate_resource_failure_model_distribution(resource, mode = "repair", time_unit=time_unit)

        rel_model.add_place(p_ok)
        rel_model.add_place(p_failed)

        rel_model.add_transition(t_fail)
        rel_model.add_transition(t_repair)

        rel_model.add_output_arc(t_repair,p_ok)
        rel_model.add_input_arc(p_ok,t_fail)
        rel_model.add_output_arc(t_fail,p_failed)
        rel_model.add_input_arc(p_failed,t_repair)

        for transition in rel_model.transitions:
            if resource == transition.label.split("_")[0]:
                rel_model.add_inhibitor_arc(transition=rel_model.get_transition_by_label(transition.label),place=p_failed)

    def _estimate_resource_failure_model_distribution(self, resource, mode, time_unit, export_plots = True):

        failure_times = []
        repair_times = []
        durations = []

        resource_state_log = self.state_log[self.state_log["resource"]==resource]

        failure_times = resource_state_log[resource_state_log["state"]=="failure"]["timestamp"].tolist()
        repair_times = resource_state_log[resource_state_log["state"]=="repaired"]["timestamp"].tolist()

        if mode == "repair":
            match time_unit:
                case "s":
                    durations = [(x-y).total_seconds() for x,y in zip(repair_times,failure_times)]
                case "m":
                    durations = [(x-y).total_seconds()/60 for x,y in zip(repair_times,failure_times)]
                case "h":
                    durations = [(x-y).total_seconds()//3600 for x,y in zip(repair_times,failure_times)]
                case "d":
                    durations = [(x-y).days for x,y in zip(repair_times,failure_times)]
                case _:
                    raise Exception("time_unit undefined: {}.".format(time_unit))  

            f = Fitter(durations,distributions=json.loads(self.config.get("DISTRIBUTIONS","dists")))
            f.fit()

            if export_plots == True:
                f.hist()
                f.plot_pdf(Nbest=1)
                plt.title("Fitted repair distribution " + str(resource))
                plt.xlabel(time_unit)
                plt.savefig(distributions_dir + str(resource) + "repair_dist.pdf")
                plt.clf()

        if mode == "fail":
            
            failure_times.pop(0)

            match time_unit:
                case "s":
                    durations = [(x-y).total_seconds() for x,y in zip(failure_times,repair_times)]
                case "m":
                    durations = [(x-y).total_seconds()/60 for x,y in zip(failure_times,repair_times)]
                case "h":
                    durations = [(x-y).total_seconds()//3600 for x,y in zip(failure_times,repair_times)]
                case "d":
                    durations = [(x-y).days for x,y in zip(failure_times,repair_times)]
                case _:
                    raise Exception("time_unit undefined: {}.".format(time_unit))  

            f = Fitter(durations,distributions=json.loads(self.config.get("DISTRIBUTIONS","dists")))
            f.fit()

            if export_plots == True:
                f.hist()
                f.plot_pdf(Nbest=1)
                plt.title("Fitted failure distribution " + str(resource))
                plt.xlabel(time_unit)
                plt.savefig(distributions_dir + str(resource) + "failure_dist.pdf")
                plt.clf()

        return f.get_best()
