import configparser, sys, hashlib, os, yaml

config = configparser.ConfigParser()

if not config.read('config.ini'):
    print("No config.ini found!")
    sys.exit(1)

def get_option(csection, coption):
    if config.has_option(csection, coption):
        return config.get(csection, coption)
    else: return None

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
