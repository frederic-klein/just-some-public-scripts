#!/usr/bin/env python3

import base64
import argparse
import glob
import time
import re
import pandas as pd
from pm4py.objects.log.util import dataframe_utils
from pm4py.algo.discovery.inductive import algorithm as inductive_miner
from pm4py.algo.discovery.heuristics import algorithm as heuristic_miner
from pm4py.visualization.petri_net import visualizer as pn_visualizer
from enum import StrEnum

class WriteModes(StrEnum):
    APPEND = 'a'
    REPLACE = 'w'


def dataframe_from_qwiki_log(log_dir=None):
    start_time = time.time()

    matching_lines = []
    for f in glob.iglob(log_dir+'events.*'):
        for line in open(f).readlines():
            if 'event:' in line:
                matching_lines.append(re.split('(?: info)?\s*\|\s*', line)[1:4:])
    new_df = pd.DataFrame(matching_lines, columns=['time:timestamp', 'user', 'event'])
    print(new_df)
    print(time.time()-start_time)
    print('dataframe_from_qwiki_log')

    return new_df

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

    task_dataframe[['task_id', 'case:concept:name', 'state', 'name']] = task_dataframe['event'].str.split(
        ";", expand=True,).drop([0, 2, 4, 7, 8], axis=1)

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
    dataframe = pd.concat([dataframe, task_dataframe], ignore_index=True)

    return dataframe_utils.convert_timestamp_columns_in_df(
        dataframe, timest_columns='time:timestamp').sort_values(by='time:timestamp')


# def format_dataframe(fulldataframe=None, app=None):
#     """
#     Filter for app events in Q.wiki log files
#     Note: event:TASKCHANGE currently ignored
#     """
#     dataframe = fulldataframe.copy()

#     transition_columns = ['concept:activity', 'concept:name',
#                           'currentstate:name', 'case:concept:name']

#     dataframe = dataframe[dataframe['event'].str.contains(
#         'event:TRANSITION.*:'+app, regex=True)]

#     if dataframe.empty:
#         return dataframe

#     dataframe[transition_columns] = dataframe['event'].str.split(
#         ";", expand=True,).drop([0, 4, 6], axis=1)
#     dataframe = dataframe.drop(columns=['event'])
#     for col in transition_columns:
#         dataframe[[col]] = dataframe[col].str.split(
#             ":", expand=True,).drop([0], axis=1)
#     print(time.time()-start_time)

#     return dataframe_utils.convert_timestamp_columns_in_df(
#         dataframe, timest_columns='time:timestamp').sort_values(by='time:timestamp')

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
        # return inductive_miner.apply(dataframe)
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
        '<div style="width:1200px;height:750px;overflow:hidden;position:relative;">' +
        '<iframe scrolling="no" style="position:absolute;border:0;width:1445px;left:-224px;top:-150px;height:800px;" src="/'+app_metrics+'"></iframe>' +
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
                    '<img src="data:image/png;base64,'+gviz_base64+'" />',
                    '%ENDTAB%'])

    write_to_file(abs_output_path, [
        '%TAB{"Event Log"}%',
        app_eventlog.to_html(classes=['ma-table'], index=False).encode('ascii', 'xmlcharrefreplace').decode("utf-8"),
        '%ENDTAB%',
    ])

    write_to_file(abs_output_path, ['%ENDTABPANE%', '%ENDTAB%'])


def write_to_file(mode=WriteModes.APPEND, abs_file_path=None, lines=None):
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
        "-a", "--App", help="App Name, e.g. SomeappWFG", action='append', nargs='*')
    args = parser.parse_args()

    write_to_file(WriteModes.REPLACE, args.Output, [''])

    start_time = time.time()

    dataframe = dataframe_from_qwiki_log(log_dir=args.Input)

    print('processing duration dataframe [s]: ', time.time()-start_time)

    for app in args.App[0]:
        process_app(app=app,
                    fulldataframe=dataframe, abs_output_path=args.Output)

    print('processing duration [s]: ', time.time()-start_time)

if __name__ == '__main__':
    main()
