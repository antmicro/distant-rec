from distantrec.helpers import *
from distantrec.RAC import RAC
import grpc, yaml, os
from buildgrid.client.cas import Uploader, Downloader
from buildgrid._protos.build.bazel.remote.execution.v2 import remote_execution_pb2, remote_execution_pb2_grpc
from google import auth as google_auth
from google.auth.transport import grpc as google_auth_transport_grpc
from google.auth.transport import requests as google_auth_transport_requests
from distantrec.DepGraph import DepGraphWithRemove, DepNode
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
        subdir = get_option('SETUP', 'SUBDIR')
        builddir = get_option('SETUP', 'BUILDDIR')

        dep_graph = DepGraphWithRemove(self.yaml_path, target, ["all_conda"])
        threads = []

        for i in range(num_threads):
            worker = Thread(target=self.build_target, args=(i, dep_graph))
            worker.start()
            threads.append(worker)

        for worker in threads:
            worker.join()

    def build_target(self, worker_id, dep_graph):
        print("Worker [%d]: Starting..." % worker_id)
        node = dep_graph.take()
        reapi = RAC(get_option('SETUP','SERVER')+':'+get_option('SETUP','PORT'), get_option('SETUP', 'INSTANCE'), self.lock, worker_id)
        while node != None:
            while True:
                try:
                    self.run_target(worker_id,
                            reapi,
                            node.target,
                            node.input,
                            node.deps,
                            node.exec)
                    [nall, ncomp] = dep_graph.mark_as_completed(node)
                    logger("Worker [%d]" % worker_id, "Completed [%d/%d] %s" % (ncomp, nall, node.target))
                    node = dep_graph.take()
                except Exception as e:
                    print('Worker %d error, restarting.' % worker_id )
                    print(e)
                    continue
                else:
                    break
        reapi.uploader.close()

    def run_target(self, worker_id, reapi, vtarget, vinput, vdeps, vexec):
        logger("Worker [%d]" % worker_id, "building %s" % vtarget)

        subdir = get_option('SETUP', 'SUBDIR')
        builddir = get_option('SETUP', 'BUILDDIR')
        if subdir and vexec != 'phony':
            diff_path = os.path.relpath(subdir, os.path.commonpath([subdir, builddir]))
            vexec = "cd %s && DISTANT_REC_SUBDIR=${PWD} && %s" % (diff_path, vexec)

        cmd = ["bash", "-c", vexec]
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
            if subdir and vexec =! 'phony':
                vtarget = "{}/{}".format(diff_path, vtarget)
            out = [vtarget]
            if get_option('SETUP','LOCALCACHE') == 'yes' and os.path.exists(get_option('SETUP','BUILDDIR')+"/"+vtarget): return

        if reapi != None:
            if phony == True:
                print("Phony target, no execution.")
            else:
                ofiles = reapi.action_run(cmd,
                os.getcwd(),
                out)
                if ofiles is None:
                    print("NO OUTPUT FILES")
                    return -1
                for blob in ofiles:
                    downloader = Downloader(reapi.channel, instance=reapi.instname)
                    logger("Worker [%d]" % worker_id, "Downloading %s" % blob.path);
                    downloader.download_file(blob.digest, get_option('SETUP','BUILDDIR') + "/" + blob.path, is_executable=blob.is_executable)
                    downloader.close()
        return
