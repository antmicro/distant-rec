#!/usr/bin/env python3

import sys, re, yaml
from copy import copy
from parse import parse

DEP_FILE = sys.stdin
if len(sys.argv) > 1:
    DEP_FILE = open(sys.argv[1])
PRELUDE = "## DISTANT ##"

GLOBAL_DEFINE_RULE = "global_define_rule"
WRITE_BUILD_SECTION_BEGIN = '>>>'
WRITE_BUILD_SECTION_END = '<<<'
OUTPUT = "output"
RULE = "rule"
VARIABLE_DEFINITION = "variable_definition"
EXPLICIT_DEPENDENCY = "explicit_dependency"
IMPLICIT_DEPENDENCY = "implicit_dependency"

defined_rules = {}

#print("### Dependency to YAML converter ###")
#print("### Run on: %s" % DEP_FILE)

## HELPER FUNCTIONS

def adj_line(line):
    nline = copy(line)
    nline = nline.replace(PRELUDE, "")
    return nline.strip()

def is_with_prelude(line):
    return PRELUDE in line

## GLOBAL DEFINE RULE

def is_global_define_rule(line):
    return GLOBAL_DEFINE_RULE in line

def process_global_define_rule(line):
    result = parse("{option} {name} = {command}", line)

    assert result != None

    option = result.named["option"]
    name = result.named["name"]
    command = result.named["command"]

    if not name in defined_rules:
        defined_rules[name]=command

## OUTPUT

def is_output_usefull(output):
    return ".dir" in output

def get_output(line):
    result = parse("{option} = {output}", line)
    assert result != None

    return result.named["output"]

def get_rule(line):
    result = parse("{option} = {rule}", line)
    assert result != None

    return result.named["rule"]

def get_variable_definition(line):
    result = parse("{option} '{variable}' = {definition}", line)
    assert result != None

    variable = result.named["variable"]
    definition = result.named["definition"]
    #if (definition == "' '") or (definition == "''"):
    #    definition = ""
    return {variable: definition}

def get_dependency(line):
    result = parse("{option} = {dependency}", line)
    assert result != None

    return result.named["dependency"]

## WRITE BUILD SECTION

def is_write_build_section_begin(line):
    return WRITE_BUILD_SECTION_BEGIN in line

def is_write_build_section_end(line):
    return WRITE_BUILD_SECTION_END in line

def process_write_build_section(dep_file):
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
    #print("WB_RULE: " + str(wb_rule))

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

    wb_rule = re.sub(' +', ' ', wb_rule.replace("'", ""))
    return wb_rule

def string_stream(s, separators="\n"):
    start = 0
    for end in range(len(s)):
        if s[end] in separators:
            yield s[start:end]
            start = end + 1
    if start < end:
        yield s[start:end+1]

data = ""
for line in DEP_FILE:
    if (not is_with_prelude(line)):
        continue
    data = data + line

if DEP_FILE is not sys.stdin:
    DEP_FILE.close()

stream = string_stream(data)
for line in stream:
    fline = adj_line(line)
    if is_global_define_rule(fline):
        process_global_define_rule(fline)

stream = string_stream(data)
for line in stream:
    fline = adj_line(line)
    if is_write_build_section_begin(fline):
        process_write_build_section(stream)

if DEP_FILE is not sys.stdin:
    DEP_FILE.close()


#from pprint import pprint
#pprint(defined_rules)
