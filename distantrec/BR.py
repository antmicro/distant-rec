import yaml, os, subprocess
from distantrec.helpers import *
from distantrec.RAC import RAC
from buildgrid.client.cas import Uploader, Downloader
from google import auth as google_auth
from distantrec.DepGraph import DepGraphWithRemove, DepNode
from threading import Thread, Lock

class BuildRunner:
    def __init__(self, yaml_path):

        #self.LOCAL_TARGETS = ["all_conda", "sdf_timing"]
        #self.REMOVE_TARGETS = []

        self.LOCAL_TARGETS = ['sdf_timing']
        self.REMOVE_TARGETS = ['all_conda']
        self.RETRY_TIMES = 3

        self.lock = Lock()
        self.yaml_path = yaml_path

        self.load_config()
        self.local_run()

    def load_config(self):
        self.SUBDIR       = get_option('SETUP', 'SUBDIR')
        self.BUILDDIR     = get_option('SETUP', 'BUILDDIR')
        self.SERVER       = get_option('SETUP', 'SERVER')
        self.PORT         = get_option('SETUP', 'PORT')
        self.INSTANCE     = get_option('SETUP', 'INSTANCE')
        self.LOCALCACHE   = get_option('SETUP', 'LOCALCACHE')

    def local_run(self):
        assert self.SUBDIR != ''
        cmd_prefix = "cd %s && DISTANT_REC_SUBDIR=${PWD}" % (self.SUBDIR)

        resolve_symlinks_cmd = "find -type l -exec sh -c 'PREV=$(realpath -- \"$1\") && rm -- \"$1\" && cp -ar -- \"$PREV\" \"$1\"' resolver {} \;"
        cmd = "%s && %s " % (cmd_prefix, resolve_symlinks_cmd)
        subprocess.check_call(cmd, stdout=sys.stdout, stderr=sys.stderr, shell=True)
        print("Symlinks resolved")

        for target in self.LOCAL_TARGETS:
            print("Building local target: %s", target)
            dep_graph = DepGraphWithRemove(self.yaml_path, target, self.REMOVE_TARGETS)

            node = dep_graph.take()
            while node != None:
                if node.exec != 'phony':
                    cmd = "%s && %s" % (cmd_prefix, node.exec)
                    subprocess.check_call(cmd, stdout=sys.stdout, stderr=sys.stderr, shell=True)
                [all_targets, comp_targets] = dep_graph.mark_as_completed(node)
                print("Local Worker: Completed [%d/%d] %s" % (comp_targets, all_targets, node.target))
                node = dep_graph.take()

    def run(self, target, num_threads):
        remove_list = self.LOCAL_TARGETS + self.REMOVE_TARGETS
        dep_graph = DepGraphWithRemove(self.yaml_path, target, remove_list)

        threads = []
        for i in range(num_threads):
            worker = Thread(target=self.build_target, args=(i, dep_graph))
            worker.start()
            threads.append(worker)

        for worker in threads:
            worker.join()

    def build_target(self, worker_id, dep_graph):
        logger('Worker [%d]:' % worker_id, 'Starting...')

        node = dep_graph.take()
        server_port = self.SERVER + ':' + self.PORT
        reapi = RAC(server_port, self.INSTANCE, self.lock, worker_id)

        while node != None:
            retry = 0
            while retry < self.RETRY_TIMES:
                try:
                    self.run_target(worker_id, reapi, node.target, node.input, node.deps, node.exec)

                    [all_targets, comp_targets] = dep_graph.mark_as_completed(node)
                    logger("Worker [%d]" % worker_id,
                           "Completed [%d/%d] %s" % (comp_targets, all_targets, node.target))
                    node = dep_graph.take()
                except Exception as e:
                    logger('Worker %d' % worker_id, 'error, restarting.')
                    logger('Worker %d' % worker_id, e)
                    retry += 1
                    continue
                else:
                    break

        reapi.uploader.close()

    def run_target(self, worker_id, reapi, vtarget, vinput, vdeps, vexec):
        logger("Worker [%d]" % worker_id, "building %s" % vtarget)

        if self.SUBDIR and vexec != 'phony':
            common = os.path.commonpath([self.SUBDIR, self.BUILDDIR])
            diff_path = os.path.relpath(self.SUBDIR, common)
            vexec = "cd %s && DISTANT_REC_SUBDIR=${PWD} && %s" % (diff_path, vexec)

        phony = True if vexec == 'phony' else False

        # TODO: hack
        if self.SUBDIR != '' and vexec != 'phony':
            vtarget = "{}/{}".format(diff_path, vtarget)
        out = [vtarget]

        target_path = self.BUILDDIR + "/" + vtarget
        if self.LOCALCACHE == 'yes' and os.path.exists(target_path): return

        if reapi != None:
            if phony == True:
                print("Phony target, no execution.")
            else:
                cmd = ["bash", "-c", vexec]
                ofiles = reapi.action_run(cmd, os.getcwd(), out)

                if ofiles is None:
                    print("NO OUTPUT FILES")
                    return -1

                for blob in ofiles:
                    downloader = Downloader(reapi.channel, instance=reapi.instname)
                    logger("Worker [%d]" % worker_id, "Downloading %s" % blob.path);
                    downloader.download_file(blob.digest, self.BUILDDIR + "/" + blob.path, is_executable=blob.is_executable)
                    downloader.close()
        return
