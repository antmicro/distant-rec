#!/usr/bin/env python3

import sys

NO_SERVER = 0
if len(sys.argv) > 3:
    if sys.argv[3] == "--no-server":
        NO_SERVER = 1

if NO_SERVER == 0:
   sys.path.insert(0, "tools/buildgrid")
   import grpc
   from buildgrid.client.cas import Uploader, Downloader
   from buildgrid._protos.build.bazel.remote.execution.v2 import remote_execution_pb2, remote_execution_pb2_grpc

   from google import auth as google_auth
   from google.auth.transport import grpc as google_auth_transport_grpc
   from google.auth.transport import requests as google_auth_transport_requests

import yaml, os, configparser

def get_option(csection, coption):
    config = configparser.ConfigParser()

    exists = os.path.isfile('config.ini')
    if not exists:
        copyfile('config.ini.example','config.ini')
    config.read('config.ini')
    if config.has_option(csection, coption):
        return config.get(csection, coption)



class RAC:
    def __init__(self, uri, instance):
        if(get_option('SETUP','USERBE') == 'yes'):
            credentials, _ = google_auth.default()
            request = google_auth_transport_requests.Request()
            self.channel = google_auth_transport_grpc.secure_authorized_channel(credentials, request, 'remotebuildexecution.googleapis.com:443')
        else:
            self.channel = grpc.insecure_channel(uri)
        self.instname = instance
        self.uploader = Uploader(self.channel, instance=self.instname)
        if instance == None:
           nm = "unknown--"+uri
        else:
           nm = instance
        print("Running on instance {}".format(nm))

    def upload_action(self, commands, input_root, output_file, cache=True):
        command_handler = remote_execution_pb2.Command()

        for arg in commands:
            command_handler.arguments.extend([arg])

        for ofile in output_file:
            print("output_file: " + ofile)
            command_handler.output_files.extend([ofile])

        command_digest = self.uploader.put_message(command_handler, queue=True)

        input_root_digest = self.uploader.upload_directory(input_root + "/build")

        action = remote_execution_pb2.Action(command_digest=command_digest,
                input_root_digest = input_root_digest,
                do_not_cache=not cache)

        action_digest = self.uploader.put_message(action, queue=False)

        return action_digest

    def run_command(self, action_digest, cache=True):
        stub = remote_execution_pb2_grpc.ExecutionStub(self.channel)

        request = remote_execution_pb2.ExecuteRequest(instance_name="",
                action_digest=action_digest,
                skip_cache_lookup=not cache)

        response = stub.Execute(request)

        stream = None

        print(response)
        COUNT = 0
        for stream in response:
            COUNT += 1
            #print(str(stream.response.value,  encoding='utf-8', errors='ignore'))
        if COUNT != 1:
           print("WARNING: response returns more streams!")
        execute_response = remote_execution_pb2.ExecuteResponse()
        stream.response.Unpack(execute_response)
        print(str(execute_response.result.stderr_raw, errors='ignore'))
        if execute_response.result.exit_code != 0:
            print("Compilation failed.")
            fail = 1
            return None

        return execute_response.result.output_files

    def action_run(self, cmd, input_dir, output_files):
        action_digest = self.upload_action(cmd, input_dir, output_files)
        self.uploader.flush()
        return self.run_command(action_digest)

class BuildRunner:
    def __init__(self, yaml_path, reapi):
        self.config = yaml.safe_load(open(yaml_path))
        self.reapi = reapi
        self.counter = 0

    def run(self, target):
        if not target in self.config:
            print("Target {} not found".format(target));
            return
        print("Building target {}".format(target))

        if 'deps' in self.config[target]:
            for dependent in self.config[target]['deps']:
                self.run(dependent)
        if 'input' in self.config[target]:
            for dependent in self.config[target]['input']:
                if dependent in self.config:
                   if (self.run(dependent) == -1): return -1

        cmd = self.config[target]['exec'].split(' ')

        if 'output' in self.config[target]:
            out = (self.config[target]['output'],)
        else:
            out = []
            # TODO: hack
            out = [target]
            if (os.path.exists("build/"+target)): return

        if self.reapi != None:
              ofiles = self.reapi.action_run(cmd,
                os.getcwd(),
                out)
              if ofiles is None:
                  return -1
              for blob in ofiles:
               downloader = Downloader(self.reapi.channel, instance=self.reapi.instname)
               downloader.download_file(blob.digest, "build/" + blob.path, is_executable=blob.is_executable)
               downloader.close()
        else:
           self.counter += 1
           print("[DUMMY %d] " % (self.counter) + " ".join(cmd))
        return 0



if __name__ == '__main__':
    if NO_SERVER == 0:
       test = RAC(get_option('SETUP','SERVER')+':'+get_option('SETUP','PORT'), get_option('SETUP', 'INSTANCE'))
    else:
       test = None
    b = BuildRunner(sys.argv[1], test)
    b.run(sys.argv[2])
    if test != None:
       test.uploader.close()
