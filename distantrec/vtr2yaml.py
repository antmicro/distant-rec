#!/usr/bin/env python

import sys, yaml

def yaml_section(execc, deps=[]):
    section = {}
    section["exec"] = execc
    section["deps"] = deps
    section["output"] = execc[:-11]+"vpr_stdout.log"
    return section

def mangle_from_list(scripts):
    for script in scripts:
        mangle = ScriptMangler(script)
        mangle.abs_to_rel()
        mangle.temporary_folder_fix()
        mangle.sleep()
        mangle.flush()

def atr_text(text):
    # Take a string with absolute path and substitute it with "./"
    start_index = text.find("vtr_flow")
    return "./{}".format(text[start_index:])

def buildyaml(scripts):
    yaml = dict()
    for script in scripts:
        rel = atr_text(script)
        yaml[rel] = yaml_section(rel)

    yaml["tests"] = yaml_section("phony", list(yaml.keys()))
    yaml["all"] = yaml_section("phony", ["tests"])

#    yaml["make"] = yaml_section("make -j "+cores)

    return yaml


class ScriptMangler:
    def __init__(self, path):
        self.path = path
        self.file_handle = open(path, "r+")
        self.file_string = self.file_handle.read()
        self.file_list = self.file_string.split("\n")

    def abs_to_rel(self):

        arguments = self.file_list[13].split(" ")

        for i in range(4,7):
            arguments[i] = atr_text(arguments[i])

        arguments_join = " ".join(arguments)

        self.file_list[13] = arguments_join

    def temporary_folder_fix(self):
        temp_relative_path = atr_text(self.path)[:-11]
        
        arguments = self.file_list[13].split(" ")

        temp_arg = arguments.index("-temp_dir")

        arguments[temp_arg+1] = temp_relative_path

        arguments_join = " ".join(arguments)

        self.file_list[13] = arguments_join

    def sleep(self):
        self.file_list[2] = "sleep 180"

    def flush(self):
        self.file_string = "\n".join(self.file_list)
        self.file_handle.seek(0)
        self.file_handle.write(self.file_string)
        self.file_handle.close()

def main():
    scripts = open(sys.argv[1], "r")
    scripts_read = scripts.read()
    scripts_list = scripts_read.split("\n")
    scripts_list = scripts_list[:-1]  
    mangle_from_list(scripts_list)

    yaml_dict = buildyaml(scripts_list)


    yaml_file = open("vtr.yml", "w")
    yaml.dump(yaml_dict, yaml_file)

    scripts.close()
    yaml_file.close()

main()
