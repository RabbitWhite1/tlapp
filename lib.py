import codecs
import copy
import json
import random
import re
import rich
import sys
import time

import rich.progress
from extractor import Extractor, ProtocolObject
from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn, TimeElapsedColumn

import tlagraph as tg

class PathFinder:
    def __init__(self, graph: tg.TLAGraph, step_limit: int, extractor: Extractor, output_prefix: str):
        self.graph: tg.TLAGraph = graph
        self.step_limit = step_limit
        self.extractor = extractor
        self.output_prefix = output_prefix

        self.node_file = open(output_prefix + '.node', 'w')
        self.edge_file = open(output_prefix + '.edge', 'w')
        self.message_file = open(output_prefix + '.message', 'w')

        self.count = 0
        self.advancer = None


    def get_node_label(self, node_id):
        return self.graph.get_node(node_id).label
        
    def write_all_nodes(self):
        for i, node_id in enumerate(self.graph.nodes()):
            node = self.graph.get_node(node_id)
            self.node_file.write(str(node_id) + ' ' + node.label + '\n')
    
    def step_limit_dfs(self, source: tg.Edge, path: list[tuple[int, str]]):
        graph = self.graph
        if len(path)-1 >= self.step_limit or graph.num_successors(source.dst.node_id) == 0:
            self.count += 1
            if self.advancer is not None:
                self.advancer()
            self.write_one_path(path)
            return
        for edge in graph.successor_edges(source.dst.node_id):
            path.append(edge)
            self.step_limit_dfs(edge, path)
            path.pop()

    def step_limit_dfs_track(self, source: int):
        progress = Progress(TextColumn("DFS Writing Paths"), BarColumn(), 
                            TextColumn("#of paths: {task.completed}"), 
                            TimeElapsedColumn())
        task_id = progress.add_task("Path Writing", total=None)
        self.advancer = lambda : progress.advance(task_id)
        with progress:
           source_node = self.graph.get_node(source)
           faked_edge = tg.Edge(None, source_node, None)
           self.step_limit_dfs(faked_edge, [faked_edge])

    def write_one_path(self, path: list[int]):
        graph = self.graph
        prev_node = None
        diffs = []
        for i, edge in enumerate(path):
            prev_node = edge.src
            node = edge.dst
            action = edge.label
            if i == 0:
                self.edge_file.write(str(node.node_id) + ' ')
            else:
                self.edge_file.write(action + ' ' + str(node.node_id) + ' ')
                # write the diff of two nodes to message file
                assert prev_node is not None
                diffs.append(self.extractor.extract(action, prev_node.label, node.label))
        self.edge_file.write('\n')
        self.message_file.write(json.dumps(diffs, default=lambda o: None if not isinstance(o, ProtocolObject) else o.to_dict()) + '\n')

"""
Main function
"""
def main(extractor: Extractor):
    if (len(sys.argv) > 3):
        path = sys.argv[1]
        dir = sys.argv[2]
        step_limit = int(sys.argv[3])
    else:
        print('check your command')
        sys.exit(1)
    
    try:
        open(path)
    except IOError as e:
        sys.stderr.write("ERROR: could not read file" + path + "\n")
        sys.exit(1)

    start_time = time.time()
    graph = tg.TLAGraph.from_file(path)
    print(f"Successfully read graph file in {time.time() - start_time}")

    n = graph.number_of_nodes()
    e = graph.number_of_edges()
    print("The graph contains", n, "nodes and", e, "edges.")

    root = graph.root_id
    print("Found the root node:", root)

    path_finder = PathFinder(graph, step_limit, extractor, dir)
    path_finder.write_all_nodes()
    path_finder.step_limit_dfs_track(root)
