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

def run_command(channel, uploader_obj, commands, input_root, output_file):
    stub = remote_execution_pb2_grpc.ExecutionStub(channel)

    action_digest = upload_action(channel, uploader_obj, commands, input_root, output_file)

    request = remote_execution_pb2.ExecuteRequest(instance_name="",
            action_digest=action_digest,
            skip_cache_lookup=True)

    response = stub.Execute(request)

    stream = None

    for stream in response:
        print(stream)

    execute_response = remote_execution_pb2.ExecuteResponse()
    stream.response.Unpack(execute_response)

if __name__ == '__main__':
    channel = grpc.insecure_channel('localhost:50051')
    upme = Uploader(channel)
    run_command(channel, upme, ['./test.sh'], sys.argv[1], [])
    upme.flush()
    upme.close()
