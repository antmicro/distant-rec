# Distant Remote Execution Client

This is the client for the Remote Execution API. It interacts with CAS and ActionCache to seamlessly build targets.

The REAPI Client uses project dependencies described in a YAML file to distribute builds to build systems that implement https://github.com/bazelbuild/remote-apis. Please inspect the `example.yml` file to get familiar with its schema.

The REAPI Client has been tested with [Google Remote Build Execution platform](https://cloud.google.com/sdk/gcloud/reference/alpha/remote-build-execution). This platform is currently in alpha stage, not available to general public, but there are many open source REAPI implementations like [Buildgrid implementation](https://gitlab.com/BuildGrid/buildgrid). This REAPI implementation can be easily installed on the local environment or virtual machines provided by many cloud service vendors. An installation guide can be found [on the Buildgrid website](https://buildgrid.gitlab.io/buildgrid/installation.html), however please be advised that you should use the modified version of Buildgrid from `tools/buildgrid` in this repo.

## Setup

Install python3 libraries from the `requirements.txt` file by running `pip install -r requirements.txt`.

This project uses additional submodules. Be sure to initialize and clone them before you proceed.

You also need to install a custom version of CMake, the sources along with the instructions are located in `tools/cmake`.

The last step is configuring the server, port and the project build folder (explained in the next section) in the `config.ini` file. An example `config.ini.example` file is in the root of the repository.


## Usage

After ensuring that the previous steps have succeeded, generate the YAML file by running `cmake <dir> -G "Ninja" | ./tools/dep2yaml/dep2yaml.py > out.yml` (where `<dir>` is the folder containing your project).

Now that the prerequisite files are ready, the execution looks as follows: `./raclient.py <dependencies yml file> target`.

The client has a possibility to dry run the build (e.g. it doesn't actually perform the build — there's no communication with the server whatsoever). To perform such a build, modify the command above by appending `--no-server`.
