#!/usr/bin/env python3

import sys
from os import listdir, chdir
from os.path import isfile, abspath

UNTIL = '/build/'
REPLACE_WITH = '/b/f/w'

def bangchange(file_path):
    script = File(file_path)

    if script.flist[0].find("#!") == 0:
        if script.flist[0].find(UNTIL) > 0:
            print("\033[92m" + "[MOD] {}".format(file_path))
            where_divide = script.flist[0].find(UNTIL)
            script.flist[0] = "#!" + REPLACE_WITH + script.flist[0][where_divide:]
            script.flush()

class File:
    def __init__(self, path):
        self.fh = open(path, "r+")
        try:
            self.fstring = self.fh.read()
        except UnicodeDecodeError:
            print("\033[94m" + "[SKP] {}".format(path))
            self.fstring = ""

        self.flist = self.fstring.split("\n")

    def flush(self):
        self.fstring = "\n".join(self.flist)
        self.fh.seek(0)
        self.fh.write(self.fstring)
        self.fh.close()

def main():
    if len(sys.argv) != 2:
        print("\033[91m"+"[FAIL] Invalid arguments")
        return 1

    chdir(sys.argv[1])
    for filename in listdir("."):
        if isfile(abspath(filename)):
            bangchange(filename)

main()
