#!/usr/bin/env python3

import grpc, sys
from buildgrid.client.cas import Uploader, Downloader
from buildgrid._protos.build.bazel.remote.execution.v2 import remote_execution_pb2, remote_execution_pb2_grpc

def fmb(channel):
    print("FMB")
    stub = remote_execution_pb2_grpc.ExecutionStub(channel)

    request = remote_execution_pb2.FindMissingBlobsRequest(instance_name="")

    response = stub.Execute(request)

    for stream in response:
        print(response)



def upload_action(channel, uploader_obj, commands, input_root, output_file):
    command_handler = remote_execution_pb2.Command()

    for arg in commands:
        command_handler.arguments.extend([arg])

    for ofile in output_file:
        print([ofile])
        command_handler.output_files.extend([ofile])

    command_digest = uploader_obj.put_message(command_handler, queue=True)

    input_root_digest = uploader_obj.upload_directory(input_root)

    action = remote_execution_pb2.Action(command_digest=command_digest,
            input_root_digest = input_root_digest,
            do_not_cache=False)

    action_digest = uploader_obj.put_message(action, queue=True)

    return action_digest

def run_command(channel, ac):
    stub = remote_execution_pb2_grpc.ExecutionStub(channel)

    request = remote_execution_pb2.ExecuteRequest(instance_name="",
            action_digest=ac,
            skip_cache_lookup=False)

    response = stub.Execute(request)

    stream = None

    for stream in response:
        print(stream)

    execute_response = remote_execution_pb2.ExecuteResponse()
    stream.response.Unpack(execute_response)

    return execute_response.result.output_files

if __name__ == '__main__':
    channel = grpc.insecure_channel('localhost:50051')
    fmb(channel)
    upme = Uploader(channel)
    down = Downloader(channel)
    ad = upload_action(channel, upme, ['./test.sh'], sys.argv[1], ('hello',))
    upme.flush()
    ofiles = run_command(channel, ad)
    print(ofiles)
    
    for blob in ofiles:
        down.download_file(blob.digest, blob.path, is_executable=blob.is_executable)

    upme.close()
    down.close()
