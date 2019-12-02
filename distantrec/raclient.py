#!/usr/bin/env python3

import sys

NO_SERVER = 0
if len(sys.argv) > 3:
    if sys.argv[3] == "--no-server":
        NO_SERVER = 1

import yaml, os, configparser, hashlib
from distantrec.RAC import RAC
from distantrec.BR import BuildRunner
from distantrec.helpers import get_option

def is_problematic(cmd):
    forbidden_chars = ['&&', '>', '>>']

    for forbidden in forbidden_chars:
        if forbidden in cmd:
            return True

    return False

def wrap_cmd(cmd):
    filename = hashlib.md5(cmd.encode())
    filename = filename.hexdigest()+".sh"

    script = open(get_option('SETUP','BUILDDIR')+"/"+filename, "w+")
    os.chmod(get_option('SETUP','BUILDDIR')+"/"+filename, 0o755)
    script.write("#!/bin/sh" + '\n')
    script.write(cmd)

    return "./"+filename

def main():
    if NO_SERVER == 0:
       test = RAC(get_option('SETUP','SERVER')+':'+get_option('SETUP','PORT'), get_option('SETUP', 'INSTANCE'))
    else:
       test = None
    b = BuildRunner(sys.argv[1], test)
    count = b.run(sys.argv[2], mock=True)
    b.run(sys.argv[2], max_count = count)
    if test != None:
       test.uploader.close()
