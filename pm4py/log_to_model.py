#!/usr/bin/env python3

import base64
import argparse
import glob
import time
import re
import pandas as pd
from pm4py.objects.log.util import dataframe_utils
from pm4py.util import constants
from pm4py.algo.discovery.inductive import algorithm as inductive_miner
from pm4py.algo.discovery.heuristics import algorithm as heuristic_miner
from pm4py.visualization.petri_net import visualizer as pn_visualizer
from pm4py.algo.organizational_mining.sna import algorithm as sna
from pm4py.visualization.sna import visualizer as sna_visualizer

from strenum import StrEnum

class WriteModes(StrEnum):
    APPEND = 'a'
    REPLACE = 'w'


def dataframe_from_qwiki_log(log_dir=None):
    matching_lines = []
    for f in glob.iglob(log_dir+'events.*'):
        for line in open(f).readlines():
            if 'event:' in line:
                matching_lines.append(re.split('(?: info)?\s*\|\s*', line)[1:4:])
    return pd.DataFrame(matching_lines, columns=['time:timestamp', 'user', 'event'])


def process_dataframe(fulldataframe=None, app=None):
    """
    Filter for app events in Q.wiki log files
    Note: event:TASKCHANGE currently ignored
    """
    dataframe = fulldataframe.copy()
    task_dataframe = fulldataframe.copy()

    transition_columns = ['concept:activity', 'concept:name',
                          'currentstate:name', 'case:concept:name']

    dataframe = dataframe[dataframe['event'].str.contains(
        'event:TRANSITION.*:'+app, regex=True)]

    if dataframe.empty:
        return dataframe

    task_dataframe = task_dataframe[task_dataframe['event'].str.contains(
        'event:TASKCHANGE.*:'+app, regex=True)]

    if not task_dataframe.empty:
        task_dataframe[['task_id', 'case:concept:name', 'state', 'name']] = task_dataframe['event'].str.split(
            ";", expand=True,).drop([0, 2, 4, 7], axis=1)

        task_dataframe['name'] = task_dataframe['name'].str.split(":", expand=True).drop([0], axis=1)
        task_dataframe['state'] = task_dataframe['state'].str.split(":", expand=True).drop([0], axis=1)
        task_dataframe['case:concept:name'] = task_dataframe['case:concept:name'].str.split(":", expand=True).drop([0], axis=1)

        task_dataframe['concept:activity'] = task_dataframe[['name', 'state']].agg(' - '.join, axis=1)
        task_dataframe['concept:name'] = task_dataframe[['name', 'state']].agg(' - '.join, axis=1)
        task_dataframe['currentstate:name'] = task_dataframe[['name', 'state']].agg(' - '.join, axis=1)

        task_dataframe = task_dataframe.drop(columns=['name', 'state', 'task_id'])
        task_dataframe = task_dataframe[['time:timestamp', 'user', 'concept:activity', 'concept:name', 'currentstate:name', 'case:concept:name', 'event' ]]

    dataframe[transition_columns] = dataframe['event'].str.split(
        ";", expand=True,).drop([0, 4, 6], axis=1)
    for col in transition_columns:
        dataframe[[col]] = dataframe[col].str.split(
            ":", expand=True,).drop([0], axis=1)

    dataframe = dataframe[['time:timestamp', 'user', 'concept:activity', 'concept:name', 'currentstate:name', 'case:concept:name', 'event' ]]
    dataframe['concept:name'] = dataframe[['concept:activity', 'concept:name']].agg(': '.join, axis=1)
    dataframe['concept:activity'] = dataframe[['concept:activity', 'concept:name']].agg(': '.join, axis=1)

    dataframe = pd.concat([dataframe, task_dataframe], ignore_index=True)

    return dataframe_utils.convert_timestamp_columns_in_df(
        dataframe, timest_columns='time:timestamp').sort_values(by='time:timestamp')


def filter_dataframe(app_eventlog=None, type='TRANSITION'):
    """
    Filter for app events in Q.wiki log files
    Note: event:TASKCHANGE currently ignored
    """
    dataframe = app_eventlog.copy()

    return dataframe[dataframe['event'].str.contains(
        'event:TRANSITION', regex=True)]


def petri_by_miner(miner_type=None, dataframe=None):
    if(miner_type == 'inductive'):
        return inductive_miner.apply(dataframe, variant=inductive_miner.Variants.IMf, parameters={
            inductive_miner.Variants.IMf.value.Parameters.NOISE_THRESHOLD: 1.0})
    elif miner_type == 'heuristic':
        return heuristic_miner.apply(dataframe)


def visualize_petri_as_base64(net=None,
                              initial_marking=None,
                              final_marking=None,
                              dataframe=None,
                              variant=pn_visualizer.Variants.WO_DECORATION,
                              extension='png'):

    gviz = pn_visualizer.apply(
        net=net,
        initial_marking=initial_marking,
        final_marking=final_marking,
        parameters={
            variant.value.Parameters.FORMAT: extension},
        variant=variant,
        log=dataframe
    )
    # https://graphviz.readthedocs.io/en/stable/examples.html
    gviz.attr(kw='graph', bgcolor='#FFFFFF')
    return base64.b64encode(pn_visualizer.serialize(gviz)).decode('utf-8')


def process_app(app=None, fulldataframe=None, abs_output_path=None):
    print(app, abs_output_path)

    app_eventlog = process_dataframe(fulldataframe=fulldataframe, app=app)

    dataframe = filter_dataframe(app_eventlog, type='TRANSITION')

    write_to_file(abs_output_path, ['%TAB{"'+app+'"}%',
                                     '%TABPANE{class="jqTabPaneFlatSub"}%'])

    app_metrics=app+'/AppMetrics'

    write_to_file(abs_output_path, [
        '%TAB{"App Metrics" encode="none"}%',
        '<p>[['+app_metrics+']['+app_metrics+']]</p>',
        '<div style="width:1200px;height:660px;overflow:hidden;position:relative;">' +
        '<iframe scrolling="no" style="position:absolute;border:0;width:1445px;left:-224px;top:-140px;height:800px;" src="/'+app_metrics+'"></iframe>' +
        '</div>',
        '%ENDTAB%',
        ])

    write_to_file(abs_output_path, [
        '%TAB{"Recommendations"}%',
        '%INCLUDE{"PmDashboardRecommendations" disablerewriteurls="on"}%',
        '%ENDTAB%',
    ])

    write_to_file(abs_output_path, [
        '%TAB{"Workflow"}%',
        '<div class="prom-large-asset"><img style="max-width:70vw;cursor:pointer;" src="/pub/Main/PmDashboard/WorkflowAppOverview.png" /></div>',
        '%ENDTAB%',
    ])

    write_to_file(abs_output_path, [
        '%TAB{"Handover of Work"}%',
        '<div style="height:3600px;">',
        '%INCLUDE{"%ATTACHURL%/data.txt.sn.txt" raw="on" literal="on" encode="none"}%',
        '</div>',
        '%ENDTAB%',
    ])

    variants = {'frequency': pn_visualizer.Variants.FREQUENCY,
                'simple': pn_visualizer.Variants.WO_DECORATION}

    for variant in variants:
        for miner_type in ['inductive', 'heuristic']:
            if dataframe.empty:
                write_to_file(abs_output_path, [
                    '%TAB{"'+miner_type+' ('+variant+')"}%',
                    'No matching log entries for this app',
                    '%ENDTAB%'])
            else:
                petri_net, initial_marking, final_marking = petri_by_miner(
                    miner_type=miner_type, dataframe=dataframe)
                gviz_base64 = visualize_petri_as_base64(net=petri_net,
                                                        initial_marking=initial_marking,
                                                        final_marking=final_marking,
                                                        variant=variants[variant],
                                                        dataframe=dataframe)
                write_to_file(abs_output_path, [
                    '%TAB{"'+miner_type+' ('+variant+')"}%',
                    '<div class="prom-large-asset"><img class="prom-large-asset" style="max-width:70vw;cursor:pointer;" src="data:image/png;base64,'+gviz_base64+'" /></div>',
                    '%ENDTAB%'])

    write_to_file(abs_output_path, [
        '%TAB{"Event Log"}%',
        app_eventlog.to_html(classes=['ma-table'], index=False).encode('ascii', 'xmlcharrefreplace').decode("utf-8"),
        '%ENDTAB%',
    ])

    write_to_file(abs_output_path, ['%ENDTABPANE%', '%ENDTAB%'])

    write_to_file(abs_output_path+'.sn.txt', handover_of_work(dataframe), mode=WriteModes.REPLACE)

def handover_of_work(log=None):
    hw_values = sna.apply(log, variant=sna.Variants.HANDOVER_LOG, parameters={constants.PARAMETER_CONSTANT_RESOURCE_KEY: 'user'})
    gviz_hw_py = sna_visualizer.apply(hw_values, variant=sna_visualizer.Variants.PYVIS)

    lines = ['']
    with open(gviz_hw_py) as f:
        lines = f.readlines()

    return lines

def write_to_file(abs_file_path=None, lines=None, mode=WriteModes.APPEND):
    f = open(file=abs_file_path, mode=mode, encoding="utf-8")
    for line in lines:
        f.write(line)
    f.close()


def main():
    parser = argparse.ArgumentParser(description='eventlog process mining')
    parser.add_argument("-o", "--Output", help="Absolute path to output file")
    parser.add_argument(
        "-i", "--Input", help="Absolute path to q.wiki eventlog folder, e.g. /fullpath/working/logs/")
    parser.add_argument(
        "-a", "--App", help="App Name, e.g. SomeappWFG or UnitARKCqGi/AbwesenheitenWFG für local MS Apps", action='append', nargs='*')
    args = parser.parse_args()

    write_to_file(args.Output, [''], WriteModes.REPLACE)

    start_time = time.time()

    dataframe = dataframe_from_qwiki_log(log_dir=args.Input)

    print('processing duration dataframe [s]: ', time.time()-start_time)

    for app in args.App[0]:
        process_app(app=app,
                    fulldataframe=dataframe, abs_output_path=args.Output)

    print('processing duration [s]: ', time.time()-start_time)

if __name__ == '__main__':
    main()
