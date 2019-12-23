#!/usr/bin/env python3

import yaml, time, os, pickle
import networkx as nx
from threading import Lock, Condition
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
        return "[%d]:%s" % (self._id, self.target)

    def __repr__(self):
        return "[%d]:%s" % (self._id, self.target)

    def __hash__(self):
        return hash(self._id)

class DepGraphPickle:
    def __init__(self, nodes, graph):
        self._nodes_dict = nodes
        self._dep_graph = graph

class DepGraph:
    def __init__(self, yaml_path, target):
        self._depyaml = None
        self._dep_graph = None
        self._nodes_dict = {}
        self._amount_all = -1
        self._amount_completed = -1

        self._nodes_order = None
        self._ready_nodes = []
        self._build_nodes = []
        self._node_ready = Condition()

        self._depyaml_path = yaml_path
        self._target = target

        cache_name = self._get_cache_name()
        if self._is_graph_cached():
            print("Load dependency graph from %s ..." % cache_name)
            measure_time(self._load_cached_graph)
        else:
            print("Parse YAML input file...")
            measure_time(self._read_yaml_file)

            print("Initialize dependency graph...")
            measure_time(self._initialize_graph)

        if not self._is_graph_cached():
            print("Save graph to %s ..." % cache_name)
            measure_time(self._save_graph_to_cache)

        print("Prepare graph...")
        measure_time(self._prepare_graph)

    ### HELPER METHODS ###

    def _read_yaml_file(self):
        assert self._depyaml_path != None

        with open(self._depyaml_path) as fd:
            self._depyaml = yaml.safe_load(fd)

    def _initialize_graph(self):
        self._load_nodes_to_dict()
        self._create_dep_graph()

    def _prepare_graph(self):
        self._simplify_graph()
        self._prepare_compilation()

        self._amount_all = self._dep_graph.number_of_nodes()
        self._amount_completed = 0

    def _load_nodes_to_dict(self):
        assert self._depyaml != None

        for key in self._depyaml.keys():
            vtarget = key

            vexec   = self._depyaml[key]["exec"]
            vdeps   = self._depyaml[key]["deps"] if "deps" in self._depyaml[key] else None
            vinputs = self._depyaml[key]["input"] if "input" in self._depyaml[key] else None

            assert (vtarget in self._nodes_dict.keys()) == False, "Duplicated target found"
            node = DepNode(vtarget, vdeps, vexec, vinputs)
            self._nodes_dict.update({vtarget:node})

        del self._depyaml
        self._depyaml = None

    def _create_dep_graph(self):
        assert self._nodes_dict != None

        self._dep_graph = nx.DiGraph()

        # Add all nodes to graph
        for node in self._nodes_dict.values():
            self._dep_graph.add_node(node)

        # Add proper edges
        for node in self._nodes_dict.values():
            if node.input != None and bool(node.input) == True:
                for dep_target in node.input:
                    if dep_target in self._nodes_dict.keys():
                        self._dep_graph.add_edge(node, self._nodes_dict[dep_target])
            if node.deps != None and bool(node.deps) == True:
                for dep_target in node.deps:
                    if dep_target in self._nodes_dict.keys():
                        self._dep_graph.add_edge(node, self._nodes_dict[dep_target])

        # Check if dependencies have no cycles
        assert nx.is_directed_acyclic_graph(self._dep_graph) == True

    def _simplify_graph(self):
        assert self._target != None

        reachable_nodes = list(nx.descendants(self._dep_graph, self._nodes_dict[self._target]))
        reachable_nodes += [self._nodes_dict[self._target]]

        unreachable_nodes = []
        for node in self._nodes_dict.values():
            if not node in reachable_nodes:
                unreachable_nodes.append(node)

        for node in unreachable_nodes:
            del self._nodes_dict[node.target]
            self._dep_graph.remove_node(node)

        # Check if dependencies have no cycles
        assert nx.is_directed_acyclic_graph(self._dep_graph) == True

    def _update_ready_nodes(self):
       assert self._nodes_dict != None

       for node in self._nodes_order:
            if (node in self._build_nodes) or (node in self._ready_nodes):
                continue

            desc = nx.descendants(self._dep_graph, node)
            if bool(desc) == False:
                self._ready_nodes += [node]
            elif node == self._nodes_dict[self._target]:
                self._ready_nodes += [node]
            else:
                break

    def _prepare_compilation(self):
        assert self._dep_graph != None

        self._nodes_order = list(reversed(list(nx.topological_sort(self._dep_graph))))
        self._update_ready_nodes()

    ### CACHE ###

    def _save_obj(self, obj, path):
        with open(path, 'wb') as fh:
            pickle.dump(obj, fh)

    def _read_obj(self, path):
        with open(path, 'rb') as fh:
            ret = pickle.load(fh)
        return ret

    def _get_cache_name(self):
        assert self._depyaml_path != None

        mod_time = os.path.getmtime(self._depyaml_path)
        gm_time = time.gmtime(mod_time)

        time_str = time.strftime("%Y-%m-%d_%H:%M:%S", gm_time)
        yaml_name = os.path.basename(self._depyaml_path)
        return ".%s.%s.cache" % (yaml_name, time_str)

    def _is_graph_cached(self):
        cache_path = self._get_cache_name()
        return os.path.exists(cache_path)

    def _load_cached_graph(self):
        cache_name = self._get_cache_name()

        graph_pickle = self._read_obj(cache_name)
        graph = graph_pickle._dep_graph
        nodes = graph_pickle._nodes_dict

        # Is a correct graph
        assert nx.is_directed_acyclic_graph(graph) == True
        self._dep_graph = graph
        self._nodes_dict = nodes

    def _save_graph_to_cache(self):
        assert bool(self._nodes_dict) == True
        assert self._dep_graph != None

        cache_name = self._get_cache_name()

        graph_pickle = DepGraphPickle(self._nodes_dict, self._dep_graph)
        self._save_obj(graph_pickle, cache_name)

    ### PUBLIC API ###

    def is_empty(self):
        return True if len(self._nodes_order) == 0 else False

    def mark_as_completed(self, node):
        with self._node_ready:
            self._dep_graph.remove_node(node)
            self._nodes_order.remove(node)

            self._update_ready_nodes()

            if bool(self._ready_nodes) == True:
                self._node_ready.notify()
            else:
                self._node_ready.notify_all()

            self._build_nodes.remove(node)

            self._amount_completed += 1
            result = [self._amount_all, self._amount_completed]
            return result

    def take(self):
        with self._node_ready:
            while (not self._ready_nodes) and (not self.is_empty()):
                self._node_ready.wait()

            if self.is_empty():
                return None

            result = self._ready_nodes.pop(0)
            self._build_nodes += [result]
            return result

    def print_graph(self, graph=None):
        import matplotlib.pyplot as plt

        if graph == None:
            graph = self._dep_graph

        pos=nx.drawing.nx_agraph.graphviz_layout(graph)
        labels = {}
        for node in graph.nodes:
            labels.update({node: node.target})

        nx.draw(graph, pos)
        nx.draw_networkx_labels(graph, pos, labels)
        plt.show()

    def print_nodes(self):
        for node in self._dep_graph.nodes:
            print(node)

class DepGraphWithRemove(DepGraph):
    def __init__(self, yaml_path, target, remove_list=[]):
        self._targets_to_remove = remove_list

        super().__init__(yaml_path, target)

    def _remove_targets(self):
        assert self._dep_graph != None
        assert self._nodes_dict != None
        assert isinstance(self._targets_to_remove, list) == True

        for target in self._targets_to_remove:
            assert target in self._nodes_dict.keys()

            target_node = self._nodes_dict[target]
            desc = list(nx.descendants(self._dep_graph, target_node))

            for node in desc:
                if node in self._dep_graph:
                    del self._nodes_dict[node.target]
                    self._dep_graph.remove_node(node)

    def _prepare_graph(self):
        self._remove_targets()
        self._simplify_graph()
        self._prepare_compilation()

        self._amount_all = self._dep_graph.number_of_nodes()
        self._amount_completed = 0

def main():
    #dep = DepGraph("../dev.yml", "all")
    dep = DepGraphWithRemove("../arch.yml", "file_xc7_archs_artix7_devices_rr_graph_xc7a50t-basys3_test.place_delay.bin", ["all_conda"])

if __name__ == "__main__":
    main()
