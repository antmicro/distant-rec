#!/usr/bin/env python3

import grpc, sys
from buildgrid.client.cas import Uploader, Downloader
from buildgrid._protos.build.bazel.remote.execution.v2 import remote_execution_pb2, remote_execution_pb2_grpc

class RAC:
    def __init__(self, uri):
        self.channel = grpc.insecure_channel(uri)
        self.uploader = Uploader(self.channel)
        self.downloader = Downloader(self.channel)

    def upload_action(self, commands, input_root, output_file, cache=True):
        command_handler = remote_execution_pb2.Command()

        for arg in commands:
            command_handler.arguments.extend([arg])

        for ofile in output_file:
            print([ofile])
            command_handler.output_files.extend([ofile])

        command_digest = self.uploader.put_message(command_handler, queue=True)

        input_root_digest = self.uploader.upload_directory(input_root)

        action = remote_execution_pb2.Action(command_digest=command_digest,
                input_root_digest = input_root_digest,
                do_not_cache=not cache)

        action_digest = self.uploader.put_message(action, queue=True)

        return action_digest

    def run_command(self, action_digest, cache=True):
        stub = remote_execution_pb2_grpc.ExecutionStub(self.channel)

        request = remote_execution_pb2.ExecuteRequest(instance_name="",
                action_digest=action_digest,
                skip_cache_lookup=not cache)

        response = stub.Execute(request)

        stream = None

        for stream in response:
            print(stream)

        execute_response = remote_execution_pb2.ExecuteResponse()
        stream.response.Unpack(execute_response)

        return execute_response.result.output_files

    def action_run(self, cmd, input_dir, output_files):
        action_digest = self.upload_action(cmd, input_dir, output_files)
        self.uploader.flush()
        return self.run_command(action_digest)

if __name__ == '__main__':
    test = RAC('localhost:50051')
    ofiles = test.action_run(['./test.sh'], sys.argv[1], ('hello',))
    print(ofiles)

    for blob in ofiles:
        test.downloader.download_file(blob.digest, blob.path, is_executable=blob.is_executable)

    test.uploader.close()
    test.downloader.close()
