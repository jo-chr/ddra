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

import numpy as np
import copy
import statistics
import datetime
import scipy.stats as st

from ModelManipulator import ModelManipulator

class ModelValidator:

    def __init__(self, spn:SPN, time_unit, event_log, state_log):
        self.spn = spn
        self.time_unit = time_unit
        self.event_log = event_log
        self.state_log = state_log

    def input_output_transformation(self, nr_replications, time, results_transition, warm_start, warm_start_time):
        
        y_r = []
        for i in range(nr_replications):
            spn = copy.deepcopy(self.spn) #copy self.spn without creating reference; otherwise state of spn of previous simulation run will be used for next simulation run
            if warm_start == True:
                mm = ModelManipulator()
                spn = mm.model_warm_up(spn,warm_start_time)
                simulate(spn, max_time = time, start_time = warm_start_time, time_unit = self.time_unit, verbosity = 0, protocol = False)
            else:
                simulate(spn, max_time = time, start_time = 0, time_unit = self.time_unit, verbosity = 0, protocol = False)

            if isinstance(results_transition, list):
                x = 0
                for transition in results_transition:
                    x += spn.get_transition_by_label(transition).n_times_fired
                y_r.append(x)
            else: y_r.append(spn.get_transition_by_label(results_transition).n_times_fired)
    
        print("Simulation results: {}".format(y_r))
        y_mean = np.mean(y_r)
        print("Mean: {}".format(y_mean))
        y_variance = round(statistics.variance(y_r),2)
        print("Variance: {}".format(y_variance))
        y_stdev = round(statistics.stdev(y_r),2)
        print("Standard deviation: {}".format(y_stdev))

        ci = st.t.interval(alpha=0.95,df=len(y_r)-1, loc=np.mean(y_r),scale=st.sem(y_r))
        print("[{}, {}]".format(round(ci[0],2),round(ci[1],2)))

        ground_truth, gt_mean, gt_ci = self.calculate_ground_truth(time, mode = "order_completed")
        print("Ground Truth: {}".format(ground_truth))
        print("Ground Truth Mean: {}".format(gt_mean))
        print("Ground Truth CI: {}".format(gt_ci))

        return ci, y_mean

    def calculate_ground_truth(self, time, mode):

        el_total_time = self.event_log["timestamp"][len(self.event_log["timestamp"]) - 1] - self.event_log["timestamp"][0]

        match self.time_unit:
            case "s":
                time_multiplier = el_total_time.total_seconds() // time
            case "m":
                time_multiplier = int((el_total_time.total_seconds()//60) // time)
            case "h":
                time_multiplier = el_total_time.hours // time
            case "d":
                time_multiplier = el_total_time.days // time
            case _:
                raise Exception("time_unit undefined: {}.".format(self.time_unit))    

        start_time = self.event_log["timestamp"][0]

        ground_truth = []

        print(time_multiplier)

        for i in range(time_multiplier):

            match self.time_unit:
                case "s":
                    end_time = start_time + datetime.timedelta(seconds=time)
                case "m":
                    end_time = start_time + datetime.timedelta(minutes=time)
                case "h":
                    end_time = start_time + datetime.timedelta(hours=time)
                case "d":
                    end_time = start_time + datetime.timedelta(days=time)
                case _:
                    raise Exception("time_unit undefined: {}.".format(self.time_unit))  

            
            event_log_subset = self.event_log[(self.event_log['timestamp'] >= start_time) & (self.event_log['timestamp'] <= end_time)]
            start_time = end_time

            if mode == "order_completed":
                ground_truth.append(len(event_log_subset["event"][event_log_subset["event"]=="order_completed"]))

        ground_truth
        gt_mean = np.mean(ground_truth)
        gt_ci = st.t.interval(alpha=0.95,df=len(ground_truth)-1, loc=np.mean(ground_truth),scale=st.sem(ground_truth))

        return ground_truth, gt_mean, gt_ci

