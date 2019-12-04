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


def wrap_cmd(cmd):
    filename = hashlib.md5(cmd.encode())
    filename = filename.hexdigest()+".sh"

    script = open(get_option('SETUP','BUILDDIR')+"/"+filename, "w+")
    os.chmod(get_option('SETUP','BUILDDIR')+"/"+filename, 0o755)
    script.write("#!/bin/sh" + '\n')
    script.write(cmd)

    return "./"+filename

def main():
    threads_amount = 10
    b = BuildRunner(sys.argv[1])
    b.run(sys.argv[2], threads_amount)
