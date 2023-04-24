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
import scipy.stats as st

from ModelManipulator import ModelManipulator

class ModelValidator:

    def __init__(self, spn:SPN, time_unit):
        self.spn = spn
        self.time_unit = time_unit

    def input_output_transformation(self, nr_replications, time, results_place, ground_truth, warm_start, warm_start_time):
        
        y_r = []
        for i in range(nr_replications):
            spn = copy.deepcopy(self.spn) #copy self.spn without creating reference; otherwise state of spn of previous simulation run will be used for next simulation run
            if warm_start == True:
                mm = ModelManipulator()
                spn = mm.model_warm_up(spn,warm_start_time)
                simulate(spn, max_time = time, start_time = warm_start_time, time_unit = self.time_unit, verbosity = 0, protocol = False)
            else:
                simulate(spn, max_time = time, start_time = 0, time_unit = self.time_unit, verbosity = 0, protocol = False)

            if isinstance(results_place, list):
                x = 0
                for place in results_place:
                    x += spn.get_place_by_label(place).time_non_empty
                y_r.append(x)
            else: y_r.append(spn.get_place_by_label(results_place).time_non_empty)
    
        print("Simulation results: {}".format(y_r))
        y_mean = np.mean(y_r)
        print("Mean: {}".format(y_mean))
        print("Ground Truth: {}".format(ground_truth))
        y_variance = round(statistics.variance(y_r),2)
        print("Variance: {}".format(y_variance))
        y_stdev = round(statistics.stdev(y_r),2)
        print("Standard deviation: {}".format(y_stdev))

        ci = st.t.interval(alpha=0.95,df=len(y_r)-1, loc=np.mean(y_r),scale=st.sem(y_r))
        print("[{}, {}]".format(round(ci[0],2),round(ci[1],2)))

        return ci, y_mean