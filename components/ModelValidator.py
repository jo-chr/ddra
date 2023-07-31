import numpy as np
import statistics
import datetime
import scipy.stats as st

from pyspn.components import spn, spn_simulate

#from components.ModelManipulator import ModelManipulator

class ModelValidator:

    def __init__(self, rel_model:spn.SPN, time_unit, event_log, state_log, event_log_unseen, state_log_unseen):
        self.rel_model = rel_model
        self.time_unit = time_unit
        self.event_log = event_log
        self.state_log = state_log
        self.event_log_unseen = event_log_unseen
        self.state_log_unseen = state_log_unseen

    def validate_model(self, nr_replications=10, time=1000, validation_method = "IOT", results_transition=None, results_place=None, kpi=None):

        y_r = []

        for i in range(nr_replications):

            rel_model = self.rel_model
            
            spn_simulate.simulate(rel_model, max_time = time, start_time = 0, time_unit = self.time_unit, verbosity = 0, protocol = False)

            if results_transition != None:
                if isinstance(results_transition, list):
                    x = 0
                    for transition in results_transition:
                        match kpi:
                            case "production volume" | "resource n times failed":
                                x += rel_model.get_transition_by_label(transition).n_times_fired
                            case "resource downtime":
                                x += rel_model.get_transition_by_label(transition).time_enabled
                    y_r.append(x)
                else:
                    match kpi: 
                        case "production volume" | "resource n times failed":
                            y_r.append(rel_model.get_transition_by_label(results_transition).n_times_fired)
                        case "resource downtime":
                            y_r.append(rel_model.get_transition_by_label(results_transition).time_enabled)                
                
            if results_place != None:
                if isinstance(results_place, list):
                    x = 0
                    for place in results_place:
                        match kpi:
                            case "production volume":
                                x += rel_model.get_place_by_label(place).total_tokens
                            case "resource downtime":
                                x += rel_model.get_place_by_label(place).time_non_empty
                    y_r.append(x)
                else:
                    match kpi: 
                        case "resource downtime":
                            y_r.append(rel_model.get_place_by_label(results_transition).time_non_empty)  
    
        print("--- SIMULATION RESULTS --- \n")
        print("Y: {}".format(y_r))
        y_mean = np.mean(y_r)
        print("Mean: {}".format(y_mean))
        y_variance = round(statistics.variance(y_r),2)
        print("Variance: {}".format(y_variance))
        y_stdev = round(statistics.stdev(y_r),2)
        print("Standard deviation: {}".format(y_stdev))
        ci = st.t.interval(alpha=0.95,df=len(y_r)-1, loc=np.mean(y_r),scale=st.sem(y_r))
        print("CI: {}\n".format(ci))
        
        print("--- GROUND TRUTH --- \n")
        ground_truth, gt_ci, gt_mean = self.calculate_ground_truth(time, kpi, self.event_log, self.state_log)
        print("Y: {}".format(ground_truth))
        print("Mean: {}".format(gt_mean))
        print("CI: {}\n".format(gt_ci))

        print("--- GROUND TRUTH UNSEEN --- \n")
        ground_truth_unseen, gt_ci_unseen, gt_mean_unseen = self.calculate_ground_truth(time, kpi, self.event_log_unseen, self.state_log_unseen)
        print("Y: {}".format(ground_truth_unseen))
        print("Mean: {}".format(gt_mean_unseen))
        print("CI: {}".format(gt_ci_unseen))
        
        return ci, y_mean, gt_ci, gt_mean, gt_ci_unseen, gt_mean_unseen


    def calculate_ground_truth(self, time, kpi, event_log, state_log):

        el_total_time = event_log["timestamp"][len(event_log["timestamp"]) - 1] - event_log["timestamp"][0]

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

        start_time = event_log["timestamp"][0]

        ground_truth = []

        print("n: {}".format(time_multiplier+1))

        for i in range(time_multiplier+1):

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

            event_log_subset = event_log[(event_log['timestamp'] >= start_time) & (event_log['timestamp'] <= end_time)]
            state_log_subset = state_log[(state_log['timestamp'] >= start_time) & (state_log['timestamp'] <= end_time)]            

            if kpi == "production volume":
                ground_truth.append(len(event_log_subset["event"][event_log_subset["event"]=="order_completed"]))
            if kpi == "resource n times failed":
                resources = list(state_log["resource"].unique())
                total_n_times_failed = 0
                for resource in resources:
                    n_times_failed = 0
                    resource_state_log = state_log_subset[state_log_subset["resource"]==resource]
                    n_times_failed += len(resource_state_log["state"][resource_state_log["state"]=="failure"])
                    total_n_times_failed += n_times_failed
                ground_truth.append(total_n_times_failed)
            if kpi == "resource downtime":
                resources = list(state_log["resource"].unique())
                total_system_downtime = []
                for resource in resources:
                    failure_times = []
                    repair_times = []
                    durations = []
                    total_resource_downtime = 0

                    resource_state_log = state_log_subset[state_log_subset["resource"]==resource]

                    failure_times = resource_state_log[resource_state_log["state"]=="failure"]["timestamp"].tolist()
                    repair_times = resource_state_log[resource_state_log["state"]=="repaired"]["timestamp"].tolist()

                    if len(repair_times) < len(failure_times):
                        repair_times.append(end_time)
                    if len(failure_times) < len(repair_times):
                        failure_times.insert(0,start_time)

                    if repair_times[0] < failure_times[0]:

                        failure_times.insert(0,start_time)
                        repair_times.append(end_time) 
 
                    durations = [(x-y).total_seconds()/60 for x,y in zip(repair_times,failure_times)]
                    total_resource_downtime = sum(durations)
                    total_system_downtime.append(total_resource_downtime)
                    
                ground_truth.append(sum(total_system_downtime))
            
            start_time = end_time

        ground_truth
        gt_mean = np.mean(ground_truth)
        gt_ci = st.t.interval(alpha=0.95,df=len(ground_truth)-1, loc=np.mean(ground_truth),scale=st.sem(ground_truth))

        return ground_truth, gt_ci, gt_mean

