from distantrec.helpers import get_option
import grpc, yaml, os
from buildgrid.client.cas import Uploader, Downloader
from buildgrid._protos.build.bazel.remote.execution.v2 import remote_execution_pb2, remote_execution_pb2_grpc
from google import auth as google_auth
from google.auth.transport import grpc as google_auth_transport_grpc
from google.auth.transport import requests as google_auth_transport_requests

class BuildRunner:
    def __init__(self, yaml_path, reapi):
        self.config = yaml.safe_load(open(yaml_path))
        self.reapi = reapi
        self.counter = 0

    def run(self, target, mock = False, max_count = 0):
        count = 1
        if not target in self.config:
            print("Target {} not found".format(target));
            return -1

        if 'deps' in self.config[target]:
            for dependent in self.config[target]['deps']:
                result = self.run(dependent, mock=mock, max_count = max_count)
                if (result == -1): return -1
                count += result
        if 'input' in self.config[target]:
            for dependent in self.config[target]['input']:
                if dependent in self.config:
                   result = self.run(dependent, mock=mock, max_count = max_count)
                   if (result == -1): return -1
                   count += result

        if mock:
            return count
        else:
            print("Building target {}".format(target))
        self.counter += 1
        print("[%d / %d] Executing '%s'" % (self.counter, max_count, self.config[target]['exec']))

        if get_option('SETUP','USERBE') == 'yes' and is_problematic(self.config[target]['exec']):
            cmd = [wrap_cmd(self.config[target]['exec'])]
        else:
            cmd = self.config[target]['exec'].split(' ')


        if self.config[target]['exec'] == 'phony':
            phony = True
        else:
            phony = False


        if 'output' in self.config[target]:
            out = (self.config[target]['output'],)
        else:
            out = []
            # TODO: hack
            out = [target]
            if get_option('SETUP','LOCALCACHE') == 'yes' and os.path.exists(get_option('SETUP','BUILDDIR')+"/"+target): return count

        if self.reapi != None:
            if phony == True:
                print("Phony target, no execution.")
            else:
                ofiles = self.reapi.action_run(cmd,
                os.getcwd(),
                out)
                if ofiles is None:
                    return -1
                for blob in ofiles:
                    downloader = Downloader(self.reapi.channel, instance=self.reapi.instname)
                    print("Downloading %s" % blob.path);
                    downloader.download_file(blob.digest, get_option('SETUP','BUILDDIR') + "/" + blob.path, is_executable=blob.is_executable)
                    downloader.close()
        return count
