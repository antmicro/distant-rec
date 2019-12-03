from distantrec.helpers import get_option
import grpc, yaml, os
from buildgrid.client.cas import Uploader, Downloader
from buildgrid._protos.build.bazel.remote.execution.v2 import remote_execution_pb2, remote_execution_pb2_grpc
from google import auth as google_auth
from google.auth.transport import grpc as google_auth_transport_grpc
from google.auth.transport import requests as google_auth_transport_requests
from DepTree import DepTree, DepNode
from threading import Thread
from queue import Queue

class BuildRunner:
    def __init__(self, yaml_path, reapi):
        self.config = yaml.safe_load(open(yaml_path))
        self.reapi = reapi
        self.counter = 0

        self.yaml_path = yaml_path
        self.target_queue = Queue()

    def run(self, target, num_threads):
        dep_tree = DepTree(self.yaml_path, target)

        #x_dim = len(disposed)
        #for x in range(x_dim):
        #    y_dim = len(disposed[x])
        #    for y in range(y_dim):
        #        self.target_queue.put(disposed[x][y])
        dep_tree.print_tree()
        dep_tree.print_leaves()
        threads = []
        print("num_threads: " + str(num_threads))
        for i in range(num_threads):
            worker = Thread(target=self.build_target, args=(i, dep_tree))
            worker.start()
            threads.append(worker)


        #for i in range(num_threads):
        #    self.target_queue.put(None)
        for worker in threads:
            worker.join()

    def build_target(self, worker_id, dep_tree):
        print("Worker [%d]: Starting..." % worker_id)
        node = dep_tree.take(worker_id)
        while node != None:
            dep_tree.mark_as_completed(node, worker_id)
            node = dep_tree.take(worker_id)


        #self.counter += 1
        #print("[%d / %d] Executing '%s'" % (self.counter, max_count, self.config[target]['exec']))

        #if get_option('SETUP','USERBE') == 'yes' and is_problematic(self.config[target]['exec']):
        #    cmd = [wrap_cmd(self.config[target]['exec'])]
        #else:
        #    cmd = self.config[target]['exec'].split(' ')


        #if self.config[target]['exec'] == 'phony':
        #    phony = True
        #else:
        #    phony = False


        #if 'output' in self.config[target]:
        #    out = (self.config[target]['output'],)
        #else:
        #    out = []
            # TODO: hack
        #    out = [target]
        #    if get_option('SETUP','LOCALCACHE') == 'yes' and os.path.exists(get_option('SETUP','BUILDDIR')+"/"+target): return count

        #if self.reapi != None:
        #    if phony == True:
        #        print("Phony target, no execution.")
        #    else:
        #        ofiles = self.reapi.action_run(cmd,
        #        os.getcwd(),
        #        out)
        #        if ofiles is None:
        #            return -1
        #        for blob in ofiles:
        #            downloader = Downloader(self.reapi.channel, instance=self.reapi.instname)
        #            print("Downloading %s" % blob.path);
        #            downloader.download_file(blob.digest, get_option('SETUP','BUILDDIR') + "/" + blob.path, is_executable=blob.is_executable)
        #            downloader.close()
        #return count
