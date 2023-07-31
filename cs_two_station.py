import configparser
import pandas as pd
import matplotlib.pyplot as plt

from pyspn.components import spn_visualization, spn_io

from components.ModelGenerator import ModelGenerator
from components.ModelValidator import ModelValidator
from components.ModelManipulator import ModelManipulator

config = configparser.ConfigParser()
config.read('cs_two_station.ini')

event_log = pd.read_csv('raw_data/cs_two_station/event_log.csv', sep=";", converters={"order_id":str}, parse_dates=["timestamp"], dayfirst=True)
state_log = pd.read_csv('raw_data/cs_two_station/state_log.csv', sep=";", parse_dates=["timestamp"], dayfirst=True)
event_log_unseen = pd.read_csv('raw_data/cs_two_station/event_log_unseen.csv', sep=";", converters={"order_id":str}, parse_dates=["timestamp"], dayfirst=True)
state_log_unseen = pd.read_csv('raw_data/cs_two_station/state_log_unseen.csv', sep=";", parse_dates=["timestamp"], dayfirst=True)

mg = ModelGenerator(event_log, state_log, config)
rel_model = mg.generate_model()

mv = ModelValidator(rel_model,"m",event_log,state_log,event_log_unseen,state_log_unseen)
ci, y_mean, gt_ci, gt_mean, gt_ci_unseen, gt_mean_unseen = mv.validate_model(nr_replications=100, time = 1440, results_transition="order_completed", kpi="production volume")
ci_downtime, y_mean_downtime, gt_ci_downtime, gt_mean_downtime, gt_ci_downtime_unseen, gt_mean_downtime_unseen = mv.validate_model(nr_replications=100, time = 1440, results_transition=["repair_agv1","repair_agv2","repair_cell1","repair_cell2"], kpi="resource downtime")

mm = ModelManipulator(rel_model, time_unit="m")
new_config_downtime = mm.manipulate_model(time = 1440, results_transition=["repair_agv1","repair_agv2","repair_cell1","repair_cell2"], kpi = "resource repair time", transitions_to_manipulate_dynamic=["repair_agv1","repair_agv2","repair_cell1","repair_cell2"], handicap_range_dynamic = [1.0,3.1], step_dynamic = 0.2,nr_replications=30, type_dynamic="decrease")
new_config_prod_vol = mm.manipulate_model(time = 1440, results_transition=["order_completed"], kpi = "production volume", transitions_to_manipulate_dynamic=["repair_agv1","repair_agv2","repair_cell1","repair_cell2"], handicap_range_dynamic = [1.0,3.1], step_dynamic = 0.2,nr_replications=30, type_dynamic="decrease")