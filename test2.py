#!/usr/bin/env python3

import grpc, sys
from buildgrid.client.cas import Uploader
from buildgrid._protos.build.bazel.remote.execution.v2 import remote_execution_pb2, remote_execution_pb2_grpc

def upload_action(channel, uploader_obj, commands, input_root, output_file):
    command_handler = remote_execution_pb2.Command()
    
    for arg in commands:
        command_handler.arguments.extend([arg])

    for ofile in output_file:
        command_handler.output_files.extend([ofile])

    command_digest = uploader_obj.put_message(command_handler, queue=True)

    input_root_digest = uploader_obj.upload_directory(input_root)

    action = remote_execution_pb2.Action(command_digest=command_digest,
            input_root_digest = input_root_digest,
            do_not_cache=True)

    action_digest = uploader_obj.put_message(action, queue=True)

    return action_digest

def run_command(channel, command):
    return None

if __name__ == '__main__':
    channel = grpc.insecure_channel('localhost:50051')
    upme = Uploader(channel)
    upload_action(channel, upme, ['gcc'], sys.argv[1], [])
    upme.flush()
    upme.close()
