import sys
sys.path.append('../')

try:
    from ..spn_simulator.components import spn as spn
    from ..spn_simulator.components import spn_visualization as spn_spn_visualization
    from ..spn_simulator.components import spn_simulate as spn_simulate
    from ..spn_simulator.components import spn_io as spn_io
except:
    from spn_simulator.components import spn as spn
    from spn_simulator.components import spn_visualization as spn_spn_visualization
    from spn_simulator.components import spn_simulate as spn_simulate
    from spn_simulator.components import spn_io as spn_io

import numpy as np

class ModelManipulator:

    def __init__(self):
        pass

    def model_warm_up(self, spn:spn.SPN, time):
        
        spn_simulate.simulate(spn, max_time = time, verbosity = 0, protocol = False)
        spn_simulate.reset_state(spn)
        return spn