#!/usr/bin/env python3

import os, sys, re, yaml
import argparse, pathlib
from copy import copy
from parse import parse

defined_rules = {}

def process_write_build_section(dep_file, directory):
    wb_output_list = []
    wb_rule = None
    wb_definitions = {}
    wb_explicit_deps_list = []
    wb_implicit_deps_list = []

    something_usefull = False
    for line in dep_file:
        if is_write_build_section_end(line):
            break

        fline = adj_line(line)
        option = fline.split(' ')[0]

        if (option == OUTPUT):
            output = get_output(fline);
            wb_output_list += [output]

        if (option == RULE):
            wb_rule = get_rule(line)

        if (option == VARIABLE_DEFINITION):
            vd = get_variable_definition(line)
            wb_definitions.update(vd)

        if (option == EXPLICIT_DEPENDENCY):
            wb_explicit_deps_list += [get_dependency(line)]

        if (option == IMPLICIT_DEPENDENCY):
            wb_implicit_deps_list += [get_dependency(line)]

    #print("##################################################################")
    #print("OUTPUTS: " + str(wb_output_list))
    #print("WB_RULE: " + str(wb_rule))
    #print("DEFINITIONS: " + str(wb_definitions))
    #print("EXP DEP: " + str(wb_explicit_deps_list))

    wb_rule = resolve_wb_rule(wb_output_list, wb_rule, wb_definitions, wb_explicit_deps_list)

    tmp_list = []

    root_dir = os.getcwd()
    dir_abs = os.path.abspath(directory)
    dir_path = os.path.relpath(root_dir, dir_abs)
    print("### DIR_PATH: " + str(dir_path))
    for i in range(len(wb_implicit_deps_list)):
        path = wb_implicit_deps_list[i]
        if os.path.exists(path):
            abs_path = os.path.abspath(path)
            common = os.path.commonpath([abs_path, root_dir])

            if common == "/":
                continue

            result = os.path.join(dir_path, os.path.relpath(abs_path, root_dir))
            #print("RESULT:" + str(result))
            #print("PATH: " + str(abs_path))
            #print("ROOT: " + root_dir)

            wb_implicit_deps_list[i] = result

    wb_rule = wb_rule.replace(directory, '')

    if len(wb_output_list) == 1:
        write_to_yaml(wb_explicit_deps_list, wb_output_list, wb_rule, wb_implicit_deps_list)

def write_to_yaml(inputs, outputs, rule, deps):
    assert len(outputs) == 1

    deps_inner = {}
    if bool(inputs):
        deps_inner["input"] = inputs

    deps_inner["exec"] = rule
    deps_inner["deps"] = deps

    deps = {}
    deps[outputs[0]] = deps_inner

    print(yaml.dump(deps))


def resolve_wb_rule(wb_output_list, wb_rule, wb_definitions, wb_explicit_deps_list):

    #print(wb_definitions)
    if wb_rule in defined_rules:
        #print("rule in defined rules!")
        wb_rule = defined_rules[wb_rule]
        #print("NEW RULE: " + str(wb_rule))
        rule_parts = wb_rule.split(' ')
        for part in rule_parts:
            #print("PART: " + str(part))
            if "$" in part:
                var = part.replace("$", '')
                var = var.replace("'", "")
                #print("VAR: " + str(var))
                if var in wb_definitions:
                    #print("VAR in definitions!")
                    #print("BEFORE: " + str(wb_rule))
                    wb_rule = wb_rule.replace(part, wb_definitions[var])
                    #print("AFTER: " +str(wb_rule))
    elif wb_rule in wb_definitions:
        var = wb_rule.replace("$", '')
        wb_rule = wb_definitions[var]

    if "$out" in wb_rule:
        assert len(wb_output_list) == 1
        wb_rule = wb_rule.replace("$out", wb_output_list[0])

    if "$in" in wb_rule:
        in_file = " ".join(wb_explicit_deps_list)
        wb_rule = wb_rule.replace("$in", in_file)

    # Remove the : from begining and end
    #print("### BEFORE REMOVING|" + str(wb_rule))
    wb_rule = wb_rule.strip()
    wb_rule = re.sub('^%s' % ": &&", '', wb_rule)
    wb_rule = wb_rule.replace(" : &&", '')
    wb_rule = wb_rule.strip()
    wb_rule = re.sub('%s$' % "&& :", '', wb_rule)
    wb_rule = re.sub(' +', ' ', wb_rule)
    wb_rule = wb_rule.strip()
    #print("### AFTER REMOVING &&|" + str(wb_rule))
    return wb_rule

class Dep2YAML:

    PRELUDE = "## DISTANT ##"
    GLOBAL_DEFINE_RULE = "global_define_rule"
    WRITE_BUILD_SECTION_BEGIN = '>>>'
    WRITE_BUILD_SECTION_END = '<<<'
    OUTPUT = "output"
    RULE = "rule"
    VARIABLE_DEFINITION = "variable_definition"
    EXPLICIT_DEPENDENCY = "explicit_dependency"
    IMPLICIT_DEPENDENCY = "implicit_dependency"


    ### INITIALIZATION ###

    def __init__(self, prj_dir, serv_build_dir, dep_file):

        self.root_dir = os.getcwd()
        self.prj_dir = prj_dir
        self.srv_build_dir = serv_build_dir

        self.defined_rules = {}

        self._dep_file = dep_file
        self._data = None
        self._load_data()

    def __del__(self):
        self._close_input_stream()

    def _load_data(self):
        self.data = ""
        for line in self._dep_file:
            if (not self._is_with_prelude(line)):
                continue
            self.data = self.data + line

    def _close_input_stream(self):
        if self._dep_file is not sys.stdin:
            self._dep_file.close()

    ### HELPER METHODS ###

    def _is_with_prelude(self, line):
        return Dep2YAML.PRELUDE in line

    def _adj_line(self, line):
        nline = copy(line)
        nline = nline.replace(Dep2YAML.PRELUDE, "")
        return nline.strip()

    def _create_string_stream(self, separators="\n"):
        start = 0
        for end in range(len(self.data)):
            if self.data[end] in separators:
                yield self.data[start:end]
                start = end + 1
        if start < end:
            yield self.data[start:end+1]

    ### MAIN PROCESSING CALLS ###

    def _process_global_rule_defines(self):
        stream = self._create_string_stream()
        for line in stream:
            fline = self._adj_line(line)
            if Dep2YAML.GLOBAL_DEFINE_RULE in line:
                self._process_global_define_rule(fline)

    def _process_write_build_sections(self):
        stream = self._create_string_stream()
        for line in stream:

            fline = self._adj_line(line)
            if Dep2YAML.WRITE_BUILD_SECTION_BEGIN in line:
                self._process_write_build(stream)

    ### PROCESSING SUBCALLS ###

    def _process_global_define_rule(self, line):
        result = parse("{option} {name} = '{command}'", line)

        assert result != None

        option = result.named["option"]
        name = result.named["name"]
        command = result.named["command"]

        if not name in defined_rules:
            self.defined_rules[name] = command

    def _process_write_build(self, stream):
        wb_rule = None
        wb_output_list = []
        wb_definitions = {}
        wb_explicit_deps_list = []
        wb_implicit_deps_list = []

        for line in stream:

            if Dep2YAML.WRITE_BUILD_SECTION_END in line:
                break

            fline = self._adj_line(line)
            option = fline.split(' ')[0]

            if (option == Dep2YAML.OUTPUT):
                output = self._get_output(fline);
                wb_output_list += [output]

            if (option == Dep2YAML.RULE):
                wb_rule = self._get_rule(line)
#
#            #if (option == Dep2YAML.VARIABLE_DEFINITION):
#                vd = get_variable_definition(line)
#                wb_definitions.update(vd)
#
#            if (option == Dep2YAML.EXPLICIT_DEPENDENCY):
#                wb_explicit_deps_list += [get_dependency(line)]
#
#            if (option == Dep2YAML.IMPLICIT_DEPENDENCY):
#                wb_implicit_deps_list += [get_dependency(line)]
#

            wb_rule = resolve_wb_rule(wb_output_list, wb_rule, wb_definitions, wb_explicit_deps_list)
#            #print("WB_RULE: " + str(wb_rule))

        print(wb_rule)
#            if len(wb_output_list) == 1:
#            write_to_yaml(wb_explicit_deps_list, wb_output_list, wb_rule, wb_implicit_deps_list)

    def _get_output(self,line):
        result = parse("{option} = {output}", line)
        assert result != None

        return result.named["output"]

    def _get_rule(self, line):
        result = parse("{option} = {rule}", line)
        assert result != None

        return result.named["rule"]

    def _get_variable_definition(self, line):
        result = parse("{option} '{variable}' = {definition}", line)
        assert result != None

        variable = result.named["variable"]
        definition = result.named["definition"].strip("'")

        return {variable: definition}

    def _get_dependency(self, line):
        result = parse("{option} = {dependency}", line)
        assert result != None

        return result.named["dependency"]


    ### PUBLIC API ###

    def parse(self):
        self._process_global_rule_defines()
        self._process_write_build_sections()

def main():
    parser = argparse.ArgumentParser(
        description='Convert cmake output to dependencies')
    parser.add_argument('--prj-dir', required=True, help='Path to project directory')
    parser.add_argument('--srv-build-dir', default=None, help="Server build dir")
    parser.add_argument('dep_file', metavar='DEP_FILE', nargs='?',
        default=None, help='an integer for the accumulator')
    args = parser.parse_args()

    prj_dir = args.prj_dir
    srv_build_dir = args.srv_build_dir if args.srv_build_dir != None else os.getcwd()
    dep_file = open(args.dep_file) if args.dep_file != None else sys.stdin

    parser = Dep2YAML(prj_dir, srv_build_dir, dep_file)
    parser.parse()

if __name__ == "__main__":
    main()
