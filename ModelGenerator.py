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

import pm4py
import re


class ModelGenerator:
    
    def __init__(self, event_log, state_log):
        self.event_log = event_log
        self.state_log = state_log

    def generate_model(self):
        
        spn = SPN()
        
        net, im, fm = pm4py.discover_petri_net_alpha(self.event_log, activity_key='event', case_id_key='order_id', timestamp_key='timestamp')

        #add places from pm4py pn to custom SPN
        for place in net.places:
            if "start" not in str(place) and "end" not in str(place):
                new_place = Place(label=str(place), n_tokens=0)
                spn.add_place(new_place)

        #add transitions from pm4py pn to custom SPN
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

        return spn
        
    def estimate_arrival_time_distribution(self, export_plots = True):

        arrival_times = []
        



        