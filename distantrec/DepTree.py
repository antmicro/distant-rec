#!/usr/bin/env python3

import yaml, anytree, pickle, hashlib, os
from threading import Lock, Condition
from pprint import pprint

def measure_time(fun, *args):
    from time import time

    start = time()
    ret = fun(*args)
    end = time()

    print("  Elapsed time: " + str(round(end - start, 2)))
    return ret

class DepNode(anytree.NodeMixin):

    id = 0

    def __init__(self, vtarget, vdeps, vexec, vinput, parent=None, children=None):
        self._target = vtarget
        self._deps = vdeps
        self._exec = vexec
        self._input = vinput

        self.name = self._target
        self.parent = parent
        if children:
            self.children = children

        self._id = DepNode.id
        DepNode.id = DepNode.id + 1

        super().__init__()

    def __str__(self):
        return "[%d]:%s" % (self._id, self._target)

    def __repr__(self):
        return "[%d]:%s" % (self._id, self._target)

    def __hash__(self):
        return hash(self._id)

    def __eq__(self, other):
        if isinstance(other, DepNode):
            return self._target == other._target
        else:
            return super().__eq__(other)

class DepTree:
    def __init__(self, yaml_path, target, init=True):
        self._depyaml = None    # YAML file dictionary
        self._deproot = None    # Dependency tree
        self._nodes_dict = {}   # {target: [all_related_nodes]}
        self._ready_list = []
        self._leaves_dict = {}  # {node: 'node_target'}
        self._build_list = []   # Nodes that are in building

        if init == True:
            self._tree_lock = Lock()
            self._build_list_lock = Lock()
            self._ready_lock = Lock()
            self._leaves_ready = Condition()

            print("Checking cache...")
            is_cache_up_to_date = measure_time(self._cache_is_up_to_date, yaml_path, target)
            if (is_cache_up_to_date == True):
                print("Loading dependency tree from cache...")
                measure_time(self._load_tree_from_cache, yaml_path, target)
            else:
                print("Standard initialization...")
                self._standard_init(yaml_path, target)

    ### HELPER METHODS ###

    def _standard_init(self, yaml_path, target):
        print("Parsing YAML input file...")
        with open(yaml_path) as fd:
            self._depyaml = measure_time(yaml.safe_load, fd)

        assert target in self._depyaml

        print("Parsing dependency tree...")
        measure_time(self._parse_dep_tree, target)

        print("Prepare leaves...")
        measure_time(self._prepare_leaves)

        cache_name = self._get_cache_name(yaml_path, target)
        print("Saving dependency tree to %s ..." % cache_name)
        if not os.path.exists(cache_name):
            measure_time(self._save_tree_to_cache, yaml_path, target)

    def _prepare_leaves(self):
        for leaf in self._deproot.leaves:
            if leaf._target not in self._leaves_dict.values():
                self._leaves_dict.update({leaf: leaf._target})

    def _add_to_nodes_dict(self, node):
        if not node._target in self._nodes_dict.keys():
            nodes_list = [node]
        else:
            nodes_list = self._nodes_dict[node._target]
            nodes_list += [node]

        self._nodes_dict.update({node._target: nodes_list})

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
            self._add_to_nodes_dict(new_node)

        if "input" in self._depyaml[target]:
            for inp in vinputs:
                self._parse_dep_tree(inp, new_node)
        if "deps" in self._depyaml[target]:
            for dep in vdeps:
                self._parse_dep_tree(dep, new_node)

    def _delete_node(self, node):
        with self._leaves_ready:
            assert self._deproot != None

            if node == self._deproot:
                self._deproot = None
                self._leaves_ready.notify_all()
                return

            for dep_node in self._nodes_dict[node._target]:
                parent = dep_node.parent
                parent_children_list = list(parent.children)

                # Remove node from the parent's list
                parent_children_list.remove(node)

                # If parent has no nodes it becomes a leaf
                if not parent_children_list:
                    if (parent._target not in self._leaves_dict.values()):
                        self._leaves_dict.update({parent:parent._target})
                        self._leaves_ready.notify()

                if node in self._leaves_dict.keys():
                    del self._leaves_dict[node]

                parent.children = parent_children_list

    ### CACHE ###

    def _save_obj(self, obj, path):
        with open(path, 'wb') as fh:
            pickle.dump(obj, fh)

    def _read_obj(self, path):
        with open(path, 'rb') as fh:
            ret = pickle.load(fh)
        return ret

    def _load_tree_from_cache(self, yaml_path, target):
        cache_file_path = self._get_cache_name(yaml_path, target)
        dep = self._read_obj(cache_file_path)
        #self._depyaml      = dep._depyaml
        self._deproot      = dep._deproot
        self._nodes_dict   = dep._nodes_dict
        self._ready_list   = dep._ready_list
        self._leaves_dict  = dep._leaves_dict
        self._build_list   = dep._build_list
        self._cache_hash   = dep._cache_hash

    def _save_tree_to_cache(self, yaml_path, target):
        dep = DepTree("", "", init=False)

        #dep._depyaml      = self._depyaml
        dep._deproot      = self._deproot
        dep._nodes_dict   = self._nodes_dict
        dep._ready_list   = self._ready_list
        dep._leaves_dict  = self._leaves_dict
        dep._build_list   = self._build_list
        dep._cache_hash   = self._get_dep_hash(yaml_path, target)

        cache_name = self._get_cache_name(yaml_path, target)
        self._save_obj(dep, cache_name)

    def _hash_file(self, path, block_size=65536):
        hasher = hashlib.sha1()
        with open(path, 'rb') as afile:
            buf = afile.read(block_size)
            while len(buf) > 0:
                hasher.update(buf)
                buf = afile.read(block_size)
        return hasher.hexdigest()

    def _get_dep_hash(self, yaml_file, target):
        yaml_hash = self._hash_file(yaml_file)
        to_hash = (str(yaml_hash) + target).encode('utf-8')
        final_hash = hashlib.sha1(to_hash).hexdigest()
        return final_hash

    def _get_cache_name(self, yaml_file, target):
        final_hash = self._get_dep_hash(yaml_file, target)
        return ".%s.cache" % str(final_hash)

    def _cache_is_up_to_date(self, yaml_file, target):
        cache_file_name = self._get_cache_name(yaml_file, target)

        if os.path.exists(cache_file_name):
            return True
        #    dep = self._read_obj(cache_file_name)
        #    file_hash = self._get_dep_hash(yaml_file, target)
        #    if (dep._cache_hash == file_hash):
        #        return True
        else:
            return False

    ### PUBLIC API ###

    def print_tree(self, start_node = None):
        assert self._deproot != None
        if start_node == None:
            start_node = self._deproot
        print(anytree.RenderTree(start_node, style=anytree.ContRoundStyle()))

    def print_nodes_dict(self):
        print("Nodes dict:")
        pprint(self._nodes_dict)

    def print_leaves(self):
        assert self._deproot != None
        i = 0
        for leaf in self._leaves_dict.keys():
            print("[%d]: %s" % (i, leaf))
            i = i + 1

    def is_empty(self):
        return True if self._deproot == None else False

    def mark_as_completed(self, node):
        with self._build_list_lock:
            self._build_list.remove(node)

        with self._tree_lock:
            self._delete_node(node)

        with self._ready_lock:
            self._ready_list += [node._target]

    def take(self):
        if self.is_empty():
            return None

        with self._leaves_ready:
            while (not self._leaves_dict.keys()) and (not self.is_empty()):
                self._leaves_ready.wait()

            if self.is_empty():
                return None

            result = next(iter(self._leaves_dict.keys()))
            del self._leaves_dict[result]
            with self._build_list_lock:
                self._build_list.append(result)

            return result

def main():
    dep = DepTree("../out.yml", "all")
    dep.print_tree()

if __name__ == "__main__":
    main()
