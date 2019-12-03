#!/usr/bin/env python3

import yaml, anytree
from pprint import pprint
from threading import Lock, Condition

class DepNode(anytree.NodeMixin):
    def __init__(self, vtarget, vdeps, vexec, vinput, parent=None, children=None):
        self._target = vtarget
        self._deps = vdeps
        self._exec = vexec
        self._input = vinput

        self.name = self._target
        self.parent = parent
        if children:
            self.children = children

        super().__init__()

    def __str__(self):
        return self._target

    def __repr__(self):
        return self._target

    def __hash__(self):
        return hash(self._target)

    def __eq__(self, other):
        if isinstance(other, DepNode):
            return self._target == other._target
        else:
            return super().__eq__(other)

class DepTree:
    def __init__(self, yaml_path, target):

        self._depyaml = None    # YAML file dictionary
        self._deproot = None    # Dependency tree

        self._tree_lock = Lock()
        self._build_list_lock = Lock()
        self._leaves_ready = Condition()
        self._leaves_list = []
        self._build_list = []
        #self._ready_list = []

        with open(yaml_path) as fd:
            self._depyaml = yaml.safe_load(fd)

        assert target in self._depyaml
        self._parse_dep_tree(target)
        self._resolve_tree()

    ### HELPER METHODS ###

    def _get_children_list(self, start_node = None):
        if start_node == None:
            start_node = self._deproot

        return [[node for node in children] for children in anytree.LevelOrderGroupIter(start_node, maxlevel=2)][1]

    def _get_level_lists(self, start_node = None):
        if start_node == None:
            start_node = self._deproot

        return [[node for node in children] for children in anytree.LevelOrderGroupIter(start_node)]

    def _check_if_unique(self, node_list):
         seen = set()
         return not any(i in seen or seen.add(i) for i in node_list)

    def _parse_dep_tree(self, target, node=None):
        assert self._depyaml != None

        if target not in self._depyaml:
            return

        vdeps = None
        if "deps" in self._depyaml[target]:
            vdeps = self._depyaml[target]["deps"]
        vinputs = None
        if "input" in self._depyaml[target]:
            vinputs = self._depyaml[target]["input"]
        vexec = self._depyaml[target]["exec"]

        if node == None:
            new_node = DepNode(target, vdeps, vexec, vinputs)
            self._deproot = new_node
        else:
            new_node = DepNode(target, vdeps, vexec, vinputs, parent=node)

        if "input" in self._depyaml[target]:
            for inp in vinputs:
                self._parse_dep_tree(inp, new_node)
        if "deps" in self._depyaml[target]:
            for dep in vdeps:
                self._parse_dep_tree(dep, new_node)

        if not new_node.children:
            self._leaves_list += [new_node]

    def _delete_node(self, node):
        with self._leaves_ready:
            assert self._deproot != None

            #print("Node to delete: %s\n" % node)
            if node == self._deproot:
                self._deproot = None
                #print("Delete root")
                self._leaves_ready.notify_all()
                return

            parent = node.parent
            parent_children_list = list(parent.children)

        # Remove node from the parent's list
            parent_children_list.remove(node)

        # If parent has no nodes it becomes a leaf
            if not parent_children_list:
                self._leaves_list += [parent]
                self.print_leaves()
                self._leaves_ready.notify()

            if node in self._leaves_list:
                self._leaves_list.remove(node)

            parent.children = parent_children_list

    def _resolve_tree(self):
        assert self._deproot != None

        level_lists = self._get_level_lists()
        flattened_list = [y for x in level_lists for y in x]
        flattened_list.reverse()

        found = []
        for node in flattened_list:
            if node in found:
                self._delete_node(node)
            else:
                found += [node]

    ### PUBLIC API ###

    def print_tree(self, start_node = None):
        assert self._deproot != None
        if start_node == None:
            start_node = self._deproot
        print(anytree.RenderTree(start_node, style=anytree.ContRoundStyle()))

    def print_leaves(self):
        assert self._deproot != None
        i = 0
        for leaf in self._leaves_list:
            print("[%d]: %s" % (i, leaf))
            i = i + 1

    def simple_dispose(self):
        all_nodes = [node for node in anytree.PreOrderIter(self._deproot)]
        assert self._check_if_unique(all_nodes) == True

        result = [[node.name for node in children] for children in anytree.LevelOrderGroupIter(self._deproot)]
        result.reverse()
        return result

    def is_empty(self):
        return True if self._deproot == None else False

    def mark_as_completed(self, node, worker):
        #print("Worker [%d]: node: %s\n" % (worker, str(node)))
        #print("Worker [%d]: Build list: %s\n" % (worker, str(self._build_list)))
        with self._build_list_lock:
            #print("Worker [%d]: lock tree" % worker)
            #self._ready_list += [node]
            self._build_list.remove(node)
            #print("Worker [%d]: unlock tree" % worker)

        with self._tree_lock:
            self._delete_node(node)

    def take(self, worker):
        if self.is_empty():
            return None

        with self._leaves_ready:
            #print("Worker [%d]: lock ready" % worker)
            #print("Worker [%d]: \nList: %s" % (worker, str(self._leaves_list)))
            while (not self._leaves_list) and (not self.is_empty()):
                #print("Worker [%d]: Waiting..." % worker)
                self._leaves_ready.wait()
                #print("Worker [%d]: Resumed..." % worker)

            if self.is_empty():
                return None

            result = self._leaves_list[0]
            self._leaves_list.pop(0)
            with self._build_list_lock:
                self._build_list.append(result)

            #print("Worker [%d]: unlock ready" % worker)
            return result

def main():
    dep = DepTree("../out.yml", "all")
    dep.print_tree()
    dep.print_leaves()

if __name__ == "__main__":
    main()
