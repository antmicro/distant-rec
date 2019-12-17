#!/usr/bin/env python3

import yaml
import matplotlib.pyplot as plt
from networkx import Graph, draw
from pprint import pprint

def measure_time(fun, *args):
    from time import time

    start = time()
    ret = fun(*args)
    end = time()

    print("  Elapsed time: " + str(round(end - start, 2)))
    return ret

class DepNode():

    id = 0

    def __init__(self, vtarget, vdeps, vexec, vinput):
        self.target = vtarget
        self.deps = vdeps
        self.exec = vexec
        self.input = vinput

        self._id = DepNode.id
        DepNode.id = DepNode.id + 1

    def __str__(self):
        return "[%d]:%s" % (self._id, self._target)

    def __repr__(self):
        return "[%d]:%s" % (self._id, self._target)

    def __hash__(self):
        return hash(self._id)

class DepGraph:
    def __init__(self, yaml_path, target):
        self._depyaml = None
        self._dep_graph = None
        self._nodes_dict = {}

        self._depyaml_path = yaml_path
        self._target = target

        self._read_yaml_file()
        self._load_nodes_to_dict()
        self._create_dep_graph()

    ### HELPER METHODS ###

    def _read_yaml_file(self):
        assert self._depyaml_path != None

        print("Parsing YAML input file...")
        with open(self._depyaml_path) as fd:
            self._depyaml = measure_time(yaml.safe_load, fd)

    def _load_nodes_to_dict(self):
        assert self._depyaml != None

        print("Loading nodes to dictionary")
        for key in self._depyaml.keys():
            vtarget = key

            vexec   = self._depyaml[key]["exec"]
            vdeps   = self._depyaml[key]["deps"] if "deps" in self._depyaml[key] else None
            vinputs = self._depyaml[key]["input"] if "input" in self._depyaml[key] else None

            node = DepNode(vtarget, vdeps, vexec, vinputs)
            self._nodes_dict.update({vtarget:node})

        del self._depyaml
        self._depyaml = None

    def _create_dep_graph(self):
        self._dep_graph = Graph()

        # Add all nodes to graph
        for node in self._nodes_dict.values():
            self._dep_graph.add_node(node)

        for node in self._nodes_dict.values():
            if node.input != None:# and not node.input:
                for dep_target in node.input:
                    print("Add input")
                    self._dep_graph.add_edge(node, self._nodes_dict[dep_target])
            if node.deps != None:# and not node.deps:
                for dep_target in node.deps:
                    print("Add deps")
                    self._dep_graph.add_edge(node, self._nodes_dict[dep_target])

        pprint(self._dep_graph.edges)
        #draw(self._dep_graph)
        #plt.show()

def main():
    dep = DepGraph("../dev.yml", "all")

if __name__ == "__main__":
    main()
