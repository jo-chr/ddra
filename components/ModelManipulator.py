import numpy as np
import copy
import scipy.stats as st

from pyspn.components import spn, spn_simulate

class ModelManipulator:

    def __init__(self, rel_model, time_unit):
        self.rel_model = rel_model
        self.time_unit = time_unit

    def manipulate_model(self, results_transition, kpi, nr_replications = 10, time = 1000, transition_to_manipulate_static=None, handicap_static=None, transitions_to_manipulate_dynamic = [], handicap_range_dynamic = [1.0,1.0], step_dynamic = 0.1, type_dynamic = "reduce"):

        rel_model = copy.deepcopy(self.rel_model)

        if transition_to_manipulate_static != None:
            trans = rel_model.get_transition_by_label(transition_to_manipulate_static)
            trans.handicap = handicap_static
            trans.handicap_type = "decrease"

        results = {}
        
        for handicap in np.arange(handicap_range_dynamic[0],handicap_range_dynamic[1],step_dynamic):
            for transition in transitions_to_manipulate_dynamic:
                trans = rel_model.get_transition_by_label(transition)
                if type_dynamic == "increase":
                    trans.handicap_type = "increase"
                elif type_dynamic == "decrease":
                    trans.handicap_type = "decrease"
                trans.handicap = round(handicap,2)

            ci, y_mean = self.input_output_transformation(rel_model, nr_replications, time, results_transition, kpi)
            results[round(handicap,2)] = y_mean

        return results
    
    def input_output_transformation(self, rel_model, nr_replications, time, results_transition, kpi):    

        y_r = []
        for i in range(nr_replications):

            spn_simulate.simulate(rel_model, max_time = time, start_time = 0, time_unit = self.time_unit, verbosity = 0, protocol = False)

            if isinstance(results_transition, list):
                x = 0
                for transition in results_transition:
                    if kpi == "resource repair time" or kpi == "resource downtime":
                        x += rel_model.get_transition_by_label(transition).time_enabled
                    elif kpi == "production volume":
                        x += rel_model.get_transition_by_label(transition).n_times_fired
                y_r.append(x)   

        y_mean = np.mean(y_r)
        ci = st.t.interval(alpha=0.95,df=len(y_r)-1, loc=np.mean(y_r),scale=st.sem(y_r))

        return ci, y_mean