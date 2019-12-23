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
        print("SUBDIR: " + str(subdir))
        print("BUILDDIR: " + str(builddir))

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
                    print("Worker [%d] | Completed [%d/%d]" % (worker_id, ncomp, nall))
                    node = dep_graph.take()
                except:
                    print('Worker %d error, restarting.' % worker_id )
                    continue
                else:
                    break
        reapi.uploader.close()

    def run_local(self, worker_id, reapi, vtarget, vinput, vdeps, vexec):
        logger("Worker [%d]" % worker_id, "building %s" % vtarget)
        LOCAL_BUILD_DIR = "/media/rwinkler/hdd/Projects/remote_workspace/remote-exec_workspace/distant-rec/build/symbiflow-arch-defs"

        subdir = get_option('SETUP', 'SUBDIR')
        builddir = get_option('SETUP', 'BUILDDIR')
        if subdir and vexec != 'phony':
            diff_path = os.path.relpath(subdir, os.path.commonpath([subdir, builddir]))
            vexec = "cd %s && DISTANT_REC_SUBDIR=${PWD} && echo ${DISTANT_REC_SUBDIR} && %s" % (diff_path, vexec)

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

        import subprocess
        print("-----------------------------------------------")
        print("Executing target %s" % out)
        print("Executing command %s" % cmd)
        local_cmd = "cd %s && pwd && %s" % (LOCAL_BUILD_DIR, str(cmd[0]))
        subprocess.check_call(local_cmd, stdout=sys.stdout, stderr=sys.stderr, shell=True)

    def run_target(self, worker_id, reapi, vtarget, vinput, vdeps, vexec):
        logger("Worker [%d]" % worker_id, "building %s" % vtarget)

        subdir = get_option('SETUP', 'SUBDIR')
        builddir = get_option('SETUP', 'BUILDDIR')
        if subdir and vexec != 'phony':
            diff_path = os.path.relpath(subdir, os.path.commonpath([subdir, builddir]))
            vexec = "cd %s && DISTANT_REC_SUBDIR=${PWD} && echo ${DISTANT_REC_SUBDIR} && %s" % (diff_path, vexec)

        '''if get_option('SETUP','USERBE') == 'yes':
            cmd = ["bash", "-c", vexec]
        else:
            cmd = vexec.split(' ')'''

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
                    print("NO OUTPUT FILES")
                    return -1
                for blob in ofiles:
                    downloader = Downloader(reapi.channel, instance=reapi.instname)
                    logger("Worker [%d]" % worker_id, "Downloading %s" % blob.path);
                    downloader.download_file(blob.digest, get_option('SETUP','BUILDDIR') + "/" + blob.path, is_executable=blob.is_executable)
                    downloader.close()
        return
