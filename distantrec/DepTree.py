#!/usr/bin/env python3

import yaml, anytree

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

class DepTree:
    def __init__(self, yaml_path, target):

        self._depyaml = None    # YAML file dictionary
        self._deproot = None    # Dependency tree

        with open(yaml_path) as fd:
            self._depyaml = yaml.safe_load(fd)

        assert target in self._depyaml
        self._parse_dep_tree(target)
        self.print_dep_tree()
        self.simple_dispose(4)

    def _parse_dep_tree(self, target, node=None):

        if target not in self._depyaml:
            return

        vdeps = self._depyaml[target]["deps"]
        vexec = self._depyaml[target]["exec"]
        vinputs = self._depyaml[target]["input"]

        if node == None:
            new_node = DepNode(target, vdeps, vexec, vinputs)
            self._deproot = new_node
        else:
            new_node = DepNode(target, vdeps, vexec, vinputs, parent=node)

        for inp in vinputs:
            self._parse_dep_tree(inp, new_node)

    def print_dep_tree(self, start_node = None):
        assert self._deproot != None

        if start_node == None:
            start_node = self._deproot

        print(anytree.RenderTree(start_node, style=anytree.ContRoundStyle()))

    def _get_children_list(self, node):
        return [[node for node in children] for children in anytree.LevelOrderGroupIter(node, maxlevel=2)][1]

    def _check_if_unique(self, node_list):
         seen = set()
         return not any(i in seen or seen.add(i) for i in node_list)

    def simple_dispose(self, amount):
        # all nodes
        all_nodes = [node for node in anytree.PreOrderIter(self._deproot)]
        assert self._check_if_unique(all_nodes) == True

        result = []
        tmp_result = []

        for child in root_children:
            tmp_result += [[node for node in anytree.PreOrderIter(child)]].reverse()

        tmp_result.sort(key=len)
        print(tmp_result)

        for i in range(len(tmp_result)):
            j =
        from pprint import pprint
        pprint(tmp_result)

def main():
    dep = DepTree("../out.yml", "all")

if __name__ == "__main__":
    main()
