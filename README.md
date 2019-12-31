# Distant Remote Execution Client

This is a client for the Remote Execution API. It interacts with CAS and ActionCache to seamlessly build targets.

The Distant RE Client uses project dependencies described in a YAML file to distribute builds to build systems that implement https://github.com/bazelbuild/remote-apis. Please inspect the `example.yml` file to get familiar with its schema.

The Distant RE Client has been tested with [Google Remote Build Execution platform](https://cloud.google.com/sdk/gcloud/reference/alpha/remote-build-execution). 
This platform is currently in alpha stage, not available to general public, but there are many open source REAPI implementations like [Buildgrid](https://gitlab.com/BuildGrid/buildgrid). 
This REAPI implementation can be easily installed on the local environment or virtual machines provided by many cloud service vendors. 
An installation guide can be found [on the Buildgrid website](https://buildgrid.gitlab.io/buildgrid/installation.html).
The client uses a [modified version](https://github.com/antmicro/buildgrid) of Buildgrid.
It gets automatically installed as a dependency.

## Setup

The repository is structured as a Python package, therefore to install the client you just need to run `pip install .` and all of the dependencies will be resolved automatically.

Prior to installation, users of Ubuntu Bionic or other distributions which ship older versions of Python PIP may need to update it by running `python3 -m pip install --upgrade pip`.

This project uses additional submodules. Be sure to initialize and clone them before you proceed.

You also need to install a custom version of CMake, which is included as a submodule `tools/cmake` (it contains its own build instructions).

The last step is configuring the server, port and the project build folder (explained in the next section) in the `config.ini` file. An example `config.ini.example` file is in the root of the repository.

## Usage

Clone a project which uses CMake build system to your build folder.

After ensuring that the previous steps have succeeded, generate the YAML file by entering the build directory described in the `config.ini` file and running `cmake <dir> -G "Ninja" | dep2yaml.py > ../out.yml` (where `<dir>` is the folder containing your project).

Now that the prerequisite files are ready, the execution looks as follows: `./raclient.py <dependencies yml file> target`.

## Worker environment

To ensure the integrity and to reduce the risk of failure of the builds, the workers should have the same environment (i.e. all the necessary tools installed).
The operating system of the server usually doesn't matter as long as it is able to run Buildgrid.

In the case of RBE, please contain all the packages you need for the build (e.g. build-essential, ninja) in the Docker container wherein the build shall take place.

When setting up the workers for a self-hosted Buildgrid instance, make sure that each one is deployed with the same operating system and has the same set of utilities installed.

Moreover, in certain cases (e.g. VTR) the operating system of the client should match the operating system of the workers. 
This is because sometimes we may build some binaries on the client, and then instruct the workers to execute them.
In the case of different operating systems there might appear a mismatch of the path to a shared library or version thereof.

## Symlinks

Symlinks are not properly supported in current Remote Execution API implementations.
If your project relies on them, you need to readapt it; otherwise it will not run at all.

The presence of one symlink is enough to cause the whole build to silently fail - there will be no output from client at all.
However, an error will appear on a worker.

Feel free to inspect `tools/vtr-helper.sh` to see how we solved this problem in the case of VTR.

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
1. The content of standard output will be printed to the console and dumped to a file (change in `run_vtr_flow.pl`).

The `-d` argument produces a file which is then used by `vtr2yml` to produce an input file for the client.
More strict paths are because we cannot rely on absolute paths from the client machine, as they differ on workers.

Also please be advised that VPR should be compiled without GTK, as the library will most likely not be present on the worker machines.

Below is the guide instructing how to run the regression tests using distant-rec. 

1. Create an empty build catalog and make it your current working directory.
1. Therein, clone the VTR project from our [repository](https://github.com/antmicro/vtr-flow-distant).
1. Create a configuration file (described in the [setup](#Setup) section).
1. Change your CWD to `vtr-verilog-to-routing` and compile the software by running `make`. 
1. If there need be, get the titan benchmarks by changing your CWD to `build` and running `make get_titan_benchmarks`. Then go one directory back up (`cd ..`) and upgrade architecture files with `./dev/upgrade_vtr_archs.sh`.
1. Go back to the project root (`cd ..`).
1. There's a helper script in the tools directory in this repository. Copy `vtr-helper.sh` from there to a location for binaries (e.g. `/usr/bin/`).
1. Run `vtr-helper.sh <regression test suite>`. This will generate necessary files and remove symlinks.
1. Produce a client input file by issuing `vtr2yaml vtr-verilog-to-routing/generated_scripts.txt > vtr.yml`.
1. Now that everything is ready, start the build by running `raclient vtr.yml all`.

### Abseil - C++ Common Libraries

Abseil is an open source code collection extending the C++ standard library.

There is no need to adapt this project to work with Distant RE Client. 
Simply follow the [Usage](#Usage) section to generate the input YAML file and proceed with the remote build.

### SymbiFlow Architecture Definitions

We're currently able to compile some targets from the project using our client.

Just as a reminder - make sure that you're using our version of CMake.

In order to try it yourself, clone the [repository](https://github.com/SymbiFlow/symbiflow-arch-defs) and proceed with the following steps:

```
$ cd symbiflow-arch-defs
$ git submodule update --init --recursive
$ mkdir build
$ cd build && cmake -G "Ninja" ../ | dep2yaml > ../../out.yml
$ ninja all_conda
$ cd ../..
```

It will take a while to generate the YAML.
This is because there are a lot of targets to process.

Now we need to prepare the configuration file for the client.
The keys you need to watch out for are `LOCALTARGETS`, `REMOVETARGETS` and `SUBDIR`.

The first one will instruct the client to perform certain steps of the build locally before starting the remote execution.
The next one tells the client which targets should be skipped.
The last one sets the directory wherein the build takes place.
In the case of Symbiflow, we need to install the `sdf_timing` Conda package and skip the `all_conda` target (as it has already been executed locally in the previous step).
In addition to that, the build starts from the `build` directory.

The aforementioned keys should look as follows:

```ini
LOCALTARGETS=['sdf_timing']
REMOVETARGETS=['all_conda']
SUBDIR=symbiflow-arch-defs/build
BUILDDIR=symbiflow-arch-defs
```

Now everything is ready for the build.
We've been able to build the following targets:

1. `dram_test_64x1d_eblif` - this is a small target so you might want to try it first
1. `file_xc7_archs_artix7_devices_rr_graph_xc7a50t-basys3_test.place_delay.bin`
1. `xc7/archs/artix7/devices/xc7a50t-basys3-roi-virt/arch.timing.xml`


