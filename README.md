# Distant Remote Execution Client

This is a client for the Remote Execution API. It interacts with CAS and ActionCache to seamlessly build targets.

The Distant RE Client uses project dependencies described in a YAML file to distribute builds to build systems that implement https://github.com/bazelbuild/remote-apis. Please inspect the `example.yml` file to get familiar with its schema.

The Distant RE Client has been tested with [Google Remote Build Execution platform](https://cloud.google.com/sdk/gcloud/reference/alpha/remote-build-execution). This platform is currently in alpha stage, not available to general public, but there are many open source REAPI implementations like [Buildgrid](https://gitlab.com/BuildGrid/buildgrid). This REAPI implementation can be easily installed on the local environment or virtual machines provided by many cloud service vendors. An installation guide can be found [on the Buildgrid website](https://buildgrid.gitlab.io/buildgrid/installation.html), however please be advised that you should use the modified version of Buildgrid which is a submodule in the `tools/buildgrid` directory.

## Setup

The repository is structured as a Python package, therefore to install the client you just need to run `pip install .` and all of the dependencies will be resolved automatically.

This project uses additional submodules. Be sure to initialize and clone them before you proceed.

You also need to install a custom version of CMake, which is included as a submodule `tools/cmake` (it contains its own build instructions).

The last step is configuring the server, port and the project build folder (explained in the next section) in the `config.ini` file. An example `config.ini.example` file is in the root of the repository.

## Usage

Clone a project which uses CMake build system to your build folder.

After ensuring that the previous steps have succeeded, generate the YAML file by entering the build directory described in the `config.ini` file and running `cmake <dir> -G "Ninja" | dep2yaml.py > ../out.yml` (where `<dir>` is the folder containing your project).

Now that the prerequisite files are ready, the execution looks as follows: `./raclient.py <dependencies yml file> target`.

The client has a possibility to dry run the build (e.g. it doesn't actually perform the build — there's no communication with the server whatsoever). To perform such a build, modify the command above by appending `--no-server`.

## Worker environment

To ensure the integrity and to reduce the risk of failure of the builds, the workers should have the same environment (i.e. all the necessary tools installed).
The operating system of the server usually doesn't matter as long as it runs Buildgrid properly.

In the case of RBE, please contain all the packages you need for the build (e.g. build-essential, ninja) in the Docker container wherein the build shall take place.

When setting up the workers for a self-hosted Buildgrid instance, make sure that each one is deployed with the same operating system and has the same set of utilities installed.

Moreover, in certain cases (e.g. VTR) the operating system of the client should be the same as of the workers. This is because sometimes we may build some binaries on the client, and then instruct the workers to execute them. In the case of different operating systems there might appear a shared library path or version mismatch.

## Practical examples

Even though the client strives to be universal, it has been developed so that it fulfils the needs of certain open-source projects.
Some of them will be listed in this section for reference.

### Verilog to Routing

The VTR project provides open-source CAD tools for FPGA architecture and CAD research.
Our client is able to run the `vtr_flow` regression tests and distribute them across workers.

The VTR flow scripts had to be adapted in order to run them with distant-rec.
The following modifications have been made:

1. A new argument was introduced to `run_vtr_task.pl` - `-d` as in dry run. It doesn't run the tasks, just generates the necessary scripts and dumps their paths to `generated_scripts.txt`.
1. More strict paths for graph generation in `run_vtr_flow.pl`.

The `-d` argument produces a file which is then used by `vtr2yml` to produce an input file for the client.
More strict paths are because we cannot rely on absolute paths from the client machine, as they differ on workers.

Also please be advised that VPR should be compiled without GTK, as the library most likely will not be present on the worker machines.

Below is the guide instructing how to run the `vtr_reg_strong` tests using distant-rec. 

1. Create an empty build catalog and make it your current working directory.
1. Therein, clone the VTR project from our [repository](https://github.com/antmicro).
1. Create a configuration file (described in the [setup](#Setup) section).
1. Change your CWD to `vtr-verilog-to-routing` and compile the software by running `make`. Get the titan benchmarks by running `make get_titan_benchmarks` and upgrade architecture files with `./dev/upgrade_vtr_archs.sh`.
1. Run `./vtr_flow/scripts/run_vtr_task.pl -d -l vtr-verilog-to-routing/vtr_flow/tasks/regression_tests/vtr_reg_strong/task_list.txt`.
1. Go back to the root directory (`cd ..`).
1. Produce a client input file by issuing `vtr2yaml vtr-verilog-to-routing/generated_scripts.txt`.
1. Now that everything is ready, start the build by running `raclient vtr.yml all`.

### Abseil - C++ Common Libraries

Abseil is an open source code collection extending the C++ standard library.

There is no need to adapt this project to work with Distant RE Client. Simply follow the Usage section to generate the input YAML file and proceed with remote build. 
