from distantrec.helpers import get_option,logger,vlogger
import grpc
from buildgrid.client.cas import Uploader, Downloader
from buildgrid._protos.build.bazel.remote.execution.v2 import remote_execution_pb2, remote_execution_pb2_grpc
from google import auth as google_auth
from google.oauth2 import service_account
from google.auth.transport import grpc as google_auth_transport_grpc
from google.auth.transport import requests as google_auth_transport_requests
from distantrec.helpers import get_option
from threading import Lock

class RAC:
    def __init__(self, uri, instance, lock, worker_id):
        if(get_option('SETUP','USERBE') == 'yes'):
            credentials = service_account.Credentials.from_service_account_file(get_option('SETUP','RBECREDS'))
            scoped_credentials = credentials.with_scopes(['https://www.googleapis.com/auth/cloud-platform'])
            request = google_auth_transport_requests.Request()
            self.channel = google_auth_transport_grpc.secure_authorized_channel(scoped_credentials, request, 'remotebuildexecution.googleapis.com:443')
        else:
            self.channel = grpc.insecure_channel(uri)
        self.instname = instance
        self.lock = lock
        self.worker_id = worker_id
        self.uploader = Uploader(self.channel, instance=self.instname)
        if instance == None:
           nm = "unknown--"+uri
        else:
           nm = instance
        logger("Worker [%d]" % self.worker_id, "Running on instance {}".format(nm))

    def upload_action(self, commands, input_root, output_file, cache=True):
        command_handler = remote_execution_pb2.Command()

        for arg in commands:
            command_handler.arguments.extend([arg])

        for ofile in output_file:
            command_handler.output_files.extend([ofile])

        if get_option('SETUP', 'PROPNAME') and get_option('SETUP', 'PROPVALUE') and get_option('SETUP','USERBE') == 'yes':
            new_property = command_handler.platform.properties.add()
            new_property.name = get_option('SETUP', 'PROPNAME')
            new_property.value = get_option('SETUP', 'PROPVALUE')

        command_digest = self.uploader.put_message(command_handler, queue=True)

        #if get_option('SETUP','USERBE') == 'yes':
        #self.lock.acquire()
        #vlogger("Worker [%d]" % self.worker_id,"Uploading - lock acquired")
        vlogger("Worker [%d]" % self.worker_id,"Start potential upload.")
        input_root_digest = self.uploader.upload_directory(input_root + "/" + get_option('SETUP','BUILDDIR'),queue=False)

        vlogger("Worker [%d]" % self.worker_id,"Input root digest")
        print(input_root_digest)

        #vlogger("Worker [%d]" % self.worker_id,"Uploading - input root digest calculated")

        action = remote_execution_pb2.Action(command_digest=command_digest,
                input_root_digest = input_root_digest,
                do_not_cache=not cache)

        vlogger("Worker [%d]" % self.worker_id,"Action")
        print(action)

        action_digest = self.uploader.put_message(action, queue=False)

        vlogger("Worker [%d]" % self.worker_id,"Action digest")
        print(action_digest)

        vlogger("Worker [%d]" % self.worker_id,"Uploading - action digest calculated")
        return action_digest

    def run_command(self, action_digest, cache=True):
        vlogger("Worker [%d]" % self.worker_id,"Execution - started.")
        stub = remote_execution_pb2_grpc.ExecutionStub(self.channel)
        #vlogger("Worker [%d]" % self.worker_id,"Preparing stub finished - lock release")



        request = remote_execution_pb2.ExecuteRequest(instance_name=get_option('SETUP','INSTANCE'),
                action_digest=action_digest,
                skip_cache_lookup=not cache)

        vlogger("Worker [%d]" % self.worker_id,"Request")
        print(request)


        response = stub.Execute(request)
        #if get_option('SETUP','USERBE') == 'yes':
        #self.lock.release()

        vlogger("Worker [%d]" % self.worker_id,"Execution - finished.")

        stream = None


        for stream in response:
            continue


        execute_response = remote_execution_pb2.ExecuteResponse()
        stream.response.Unpack(execute_response)
        if execute_response.result.stdout_digest.hash:
            downloader = Downloader(self.channel, instance=self.instname)
            blob = downloader.get_blob(execute_response.result.stdout_digest)
            logger("Worker [%d]" % self.worker_id, "Execution output: "+blob.decode('utf-8'))
            downloader.close()
        if execute_response.result.stdout_raw != "":
            print(str(execute_response.result.stdout_raw, errors='ignore'))

        if execute_response.result.stderr_raw != "":
            print(str(execute_response.result.stderr_raw, errors='ignore'))
        if execute_response.result.exit_code != 0:
            logger("Worker [%d]" % self.worker_id,"Target build failed.")
            fail = 1
            return None

        if execute_response.cached_result:
            logger("Worker [%d]" % self.worker_id,"Target served from cache!")

        return execute_response.result.output_files

    def action_run(self, cmd, input_dir, output_files):
        action_digest = self.upload_action(cmd, input_dir, output_files)
        self.uploader.flush()
        return self.run_command(action_digest)
