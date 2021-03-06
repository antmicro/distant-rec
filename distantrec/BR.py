import yaml, os, subprocess, ast
from distantrec.helpers import *
from distantrec.RAC import RAC
from buildgrid.client.cas import Uploader, Downloader
from google import auth as google_auth
from distantrec.DepGraph import DepGraphWithRemove, DepNode
from threading import Thread, Lock

class BuildRunner:
    def __init__(self, yaml_path):
        self.RETRY_TIMES = 3

        self.lock = Lock()
        self.yaml_path = yaml_path

        self.load_config()
        self.local_run()
        self.targetscache = []

    def load_config(self):
        self.SUBDIR         = get_option('SETUP', 'SUBDIR')
        self.BUILDDIR       = get_option('SETUP', 'BUILDDIR')
        self.SERVER         = get_option('SETUP', 'SERVER')
        self.PORT           = get_option('SETUP', 'PORT')
        self.INSTANCE       = get_option('SETUP', 'INSTANCE')
        self.LOCALCACHE     = get_option('SETUP', 'LOCALCACHE')

        if get_option('SETUP', 'LOCALTARGETS'):
            self.LOCAL_TARGETS = ast.literal_eval(get_option('SETUP', 'LOCALTARGETS'))
        else:
            self.LOCAL_TARGETS = []

        if get_option('SETUP', 'REMOVETARGETS'):
            self.REMOVE_TARGETS = ast.literal_eval(get_option('SETUP', 'REMOVETARGETS'))
        else:
            self.REMOVE_TARGETS = []

    def local_run(self):

        if self.SUBDIR:
            cmd_prefix = "cd %s && DISTANT_REC_SUBDIR=${PWD}" % (self.SUBDIR)
        else:
            cmd_prefix = "DISTANT_REC_SUBDIR=${PWD}"

        resolve_symlinks_cmd = "find -type l -exec sh -c 'PREV=$(realpath -- \"$1\") && rm -- \"$1\" && cp -ar -- \"$PREV\" \"$1\"' resolver {} \;"
        cmd = "%s && %s " % (cmd_prefix, resolve_symlinks_cmd)
        subprocess.check_call(cmd, stdout=sys.stdout, stderr=sys.stderr, shell=True)
        logger("Local Worker", "Symlinks resolved")

        for target in self.LOCAL_TARGETS:
            logger("Local Worker", "Building local target: %s" % target)
            dep_graph = DepGraphWithRemove(self.yaml_path, target, self.REMOVE_TARGETS)

            node = dep_graph.take()
            while node != None:
                if node.exec != 'phony':
                    cmd = "%s && %s" % (cmd_prefix, node.exec)
                    subprocess.check_call(cmd, stdout=sys.stdout, stderr=sys.stderr, shell=True)
                [all_targets, comp_targets, ready] = dep_graph.mark_as_completed(node)
                logger("Local Worker", "Completed [%d/%d | %d] %s" % (comp_targets, all_targets, ready, node.target))
                node = dep_graph.take()

    def run(self, target, num_threads):
        remove_list = self.LOCAL_TARGETS + self.REMOVE_TARGETS
        dep_graph = DepGraphWithRemove(self.yaml_path, target, remove_list)

        if get_option('SETUP','TARGETSCACHE') == 'yes':
            try:
                self.targetscache = [line.rstrip('\n') for line in open('.targetscache')]
            except IOError:
                print("Targets cache not present.")
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

        if get_option('SETUP','TARGETSCACHE') == 'yes':
            while node != None:
                retry = 0
                while retry < self.RETRY_TIMES:
                    try:
                        if node.target != None and node.target not in self.targetscache:
                            self.run_target(worker_id, reapi, node.target, node.input, node.deps, node.exec)
                            with open(".targetscache", "a")as f:
                                f.write(node.target+"\n")
                                f.close()
                        else:
                            logger("Worker [%d]" % worker_id, "Target %s from local cache" % node.target)
                        [all_targets, comp_targets, ready] = dep_graph.mark_as_completed(node)
                        logger("Worker [%d]" % worker_id,
                            "Completed [%d/%d | %d] %s" % (comp_targets, all_targets, ready, node.target))
                        node = dep_graph.take()
                    except Exception as e:
                        logger('Worker %d' % worker_id, 'error, restarting.')
                        logger('Worker %d' % worker_id, e)
                        retry += 1
                        continue
                    else:
                        break
        else:
            while node != None:
                retry = 0
                while retry < self.RETRY_TIMES:
                    try:
                        self.run_target(worker_id, reapi, node.target, node.input, node.deps, node.exec)
                        [all_targets, comp_targets, ready] = dep_graph.mark_as_completed(node)
                        logger("Worker [%d]" % worker_id,
                            "Completed [%d/%d | %d] %s" % (comp_targets, all_targets, ready, node.target))
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

        if self.SUBDIR and vexec != 'phony':
            vtarget = "{}/{}".format(diff_path, vtarget)
        out = [vtarget]

        target_path = self.BUILDDIR + "/" + vtarget
        if self.LOCALCACHE == 'yes' and os.path.exists(target_path): return

        if reapi != None:
            if phony == True:
                logger("Worker [%d]" % worker_id, "Phony target, no execution.")
            else:
                cmd = ["bash", "-c", vexec]
                ofiles = reapi.action_run(cmd, os.getcwd(), out)

                if ofiles is None:
                    logger("Worker [%d]" % worker_id, "NO OUTPUT FILES")
                    return -1

                for blob in ofiles:
                    downloader = Downloader(reapi.channel, instance=reapi.instname)
                    logger("Worker [%d]" % worker_id, "Downloading %s" % blob.path);
                    downloader.download_file(blob.digest, self.BUILDDIR + "/" + blob.path, is_executable=blob.is_executable)
                    downloader.close()
        return
