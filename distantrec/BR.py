from distantrec.helpers import *
from distantrec.RAC import RAC
import grpc, yaml, os
from buildgrid.client.cas import Uploader, Downloader
from buildgrid._protos.build.bazel.remote.execution.v2 import remote_execution_pb2, remote_execution_pb2_grpc
from google import auth as google_auth
from google.auth.transport import grpc as google_auth_transport_grpc
from google.auth.transport import requests as google_auth_transport_requests
from distantrec.DepTree import DepTree, DepNode
from threading import Thread, Lock
from queue import Queue

class BuildRunner:
    def __init__(self, yaml_path):
        self.config = yaml.safe_load(open(yaml_path))
        self.counter = 0
        self.lock = Lock()
        self.yaml_path = yaml_path
        self.target_queue = Queue()

    def run(self, target, num_threads):
        dep_tree = DepTree(self.yaml_path, target)
        threads = []

        for i in range(num_threads):
            worker = Thread(target=self.build_target, args=(i, dep_tree))
            worker.start()
            threads.append(worker)

        for worker in threads:
            worker.join()

    def build_target(self, worker_id, dep_tree):
        print("Worker [%d]: Starting..." % worker_id)
        node = dep_tree.take()
        reapi = RAC(get_option('SETUP','SERVER')+':'+get_option('SETUP','PORT'), get_option('SETUP', 'INSTANCE'), self.lock, worker_id)
        while node != None:
            self.run_target(worker_id,
                            reapi,
                            node._target,
                            node._input,
                            node._deps,
                            node._exec)
            dep_tree.mark_as_completed(node)
            node = dep_tree.take()
        reapi.uploader.close()

    def run_target(self, worker_id, reapi, vtarget, vinput, vdeps, vexec):
        logger("Worker [%d]" % worker_id, "building %s" % vtarget)

        subdir = get_option('SETUP', 'SUBDIR')
        if subdir and vexec != 'phony':
            vexec = "cd {} && {}".format(subdir, vexec)

        if get_option('SETUP','USERBE') == 'yes' and is_problematic(vexec):
            cmd = [wrap_cmd(vexec)]
        else:
            cmd = vexec.split(' ')

        if vexec == 'phony':
            phony = True
        else:
            phony = False

        voutput = None
        if voutput != None:
            out = (voutput,)
        else:
            out = []
            # TODO: hack
            if subdir:
                vtarget = "{}/{}".format(subdir, vtarget)
            out = [vtarget]
            if get_option('SETUP','LOCALCACHE') == 'yes' and os.path.exists(get_option('SETUP','BUILDDIR')+"/"+vtarget): return

        if reapi != None:
            if phony == True:
                print("Phony target, no execution.")
            else:
                #print("CMD: " + str(cmd))
                #print("CWD: " + str(os.getcwd()))
                #print("OUT: " + str(out))
                ofiles = reapi.action_run(cmd,
                os.getcwd(),
                out)
                if ofiles is None:
                    return -1
                for blob in ofiles:
                    self.lock.acquire()
                    downloader = Downloader(reapi.channel, instance=reapi.instname)
                    logger("Worker [%d]" % worker_id, "Downloading %s" % blob.path);
                    downloader.download_file(blob.digest, get_option('SETUP','BUILDDIR') + "/" + blob.path, is_executable=blob.is_executable)
                    downloader.close()
                    self.lock.release()
        return
