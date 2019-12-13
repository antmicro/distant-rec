#!/usr/bin/env python3

import os, sys, re, yaml
import argparse
from copy import copy
from parse import parse

def err(*args):
    print(*args, file=sys.stderr)

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

    def __init__(self, dep_file):

        self.root_dir = os.getcwd()
        self.defined_rules = {}

        self._dep_file = dep_file
        self._data = None
        self._load_data()

    def __del__(self):
        self._close_input_stream()

    def _load_data(self):
        self.data = list(filter(lambda x: Dep2YAML.PRELUDE in x,self._dep_file.readlines()))
        self.data = "".join(self.data)

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

    def _format_rule(self, rule):

        # Remove the : from begining and end
        rule = rule.strip()
        rule = re.sub('^%s' % ": &&", '', rule)
        rule = rule.replace(" : &&", '')
        rule = rule.strip()
        rule = re.sub('%s$' % "&& :", '', rule)
        rule = re.sub(' +', ' ', rule)

        # Remove multiple spaces
        rule = rule.strip()

        return rule

    def _remove_wrong_cmake_calls(self, rule):
        commands = rule.split("&&")
        for command in commands:

            # This command causes error
            if "cmake -E rm -f" in command:
                rule = rule.replace(command, ' : ')

            # cmake have different path for our tools and server
            if "bin/cmake" in command:
                parts = command.split(' ')
                for part in parts:
                    if "bin/cmake" in part:
                        rule = rule.replace(part, "cmake")

        rule = re.sub(' +', ' ', rule)
        return rule

    def _bellongs_to_project(self, path):
        abs_path = os.path.abspath(path)
        common = os.path.commonpath([abs_path, self.root_dir])

        if common == "/":
            return False
        else:
            return True

    def _convert_to_relative_path(self, path):
        abs_path = os.path.abspath(path)
        common = os.path.commonpath([abs_path, self.root_dir])

        assert common != "/", "Assumption: path bellongs to project!"
        result = os.path.relpath(abs_path, self.root_dir)

        return result

    def _write_to_yaml(self, inputs, outputs, rule, deps):
        assert len(outputs) == 1

        deps_inner = {}
        if bool(inputs):
            deps_inner["input"] = inputs

        deps_inner["exec"] = rule
        deps_inner["deps"] = deps

        deps = {}
        deps[outputs[0]] = deps_inner

        print(yaml.dump(deps))

    def _resolve_wb_rule(self, output_list, rule, definitions, explicit_deps_list):
        if rule in self.defined_rules:
            rule = self.defined_rules[rule]
            rule_parts = rule.split(' ')
            for part in rule_parts:
                if "$" in part:
                    var = part.replace("$", '')
                    var = var.replace("'", "")
                    if var in definitions:
                        rule = rule.replace(part, definitions[var])
        elif rule in definitions:
            var = rule.replace("$", '')
            rule = definitions[var]

        if "$out" in rule:
            assert len(output_list) == 1
            rule = rule.replace("$out", output_list[0])

        if "$in" in rule:
            in_file = " ".join(explicit_deps_list)
            rule = rule.replace("$in", in_file)

        rule = self._format_rule(rule)
        rule = self._remove_wrong_cmake_calls(rule)
        rule = self._format_rule(rule)

        return rule

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

        if not name in self.defined_rules:
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

            if (option == Dep2YAML.VARIABLE_DEFINITION):
                vd = self._get_variable_definition(line)
                wb_definitions.update(vd)

            if (option == Dep2YAML.EXPLICIT_DEPENDENCY):
                wb_explicit_deps_list += [self._get_dependency(line)]

            if (option == Dep2YAML.IMPLICIT_DEPENDENCY):
                wb_implicit_deps_list += [self._get_dependency(line)]

        # Convert paths from wb_explicit_deps_list to relative
        for i in range(len(wb_explicit_deps_list)):
            dep = wb_explicit_deps_list[i]
            if os.path.exists(dep) and os.path.isabs(dep):
                if self._bellongs_to_project(dep):
                    wb_explicit_deps_list[i] = self._convert_to_relative_path(dep)

        # Convert paths from wb_implicit_deps to relative
        for i in range(len(wb_implicit_deps_list)):
            dep = wb_implicit_deps_list[i]
            if os.path.exists(dep) and os.path.isabs(dep):
                if self._bellongs_to_project(dep):
                    wb_implicit_deps_list[i] = self._convert_to_relative_path(dep)

        dependencies = wb_explicit_deps_list + wb_implicit_deps_list

        # Resolve variables in the rule
        wb_rule = self._resolve_wb_rule(wb_output_list,
                                        wb_rule,
                                        wb_definitions,
                                        dependencies)

        # Convert paths in resolved rule to relative
        rule_parts = wb_rule.split(' ')
        for part in rule_parts:
            if "=" in part:
                split_list = part.split("=")
                if len(split_list) != 2:
                    continue
                else:
                    [variable, tmp_path] = split_list
                    if os.path.exists(tmp_path) and os.path.isabs(tmp_path):
                        new_path = self._convert_to_relative_path(tmp_path)
                        wb_rule = wb_rule.replace(tmp_path, new_path)
            elif os.path.isabs(part):
                if self._bellongs_to_project(part):
                    new_path = self._convert_to_relative_path(part)
                    wb_rule = wb_rule.replace(part, new_path)

        if len(wb_output_list) == 1:
            self._write_to_yaml(wb_explicit_deps_list, wb_output_list, wb_rule, wb_implicit_deps_list)

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

        definition_parts = definition.split(' ')
        for part in definition_parts:
            if os.path.exists(part) and os.path.isabs(part):
                if self._bellongs_to_project(part):
                    new_path = self._convert_to_relative_path(part)
                    definition = definition.replace(part, new_path)

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
    parser.add_argument('dep_file', metavar='DEP_FILE', nargs='?',
        default=None, help='an integer for the accumulator')
    args = parser.parse_args()

    dep_file = open(args.dep_file) if args.dep_file != None else sys.stdin

    parser = Dep2YAML(dep_file)
    parser.parse()

if __name__ == "__main__":
    main()
