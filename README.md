# Remote Execution API Client

This is the client for the Remote Execution API. It interacts with CAS and ActionCache to seamlessly build targets.

The REAPI Client uses project dependencies described in a YAML file to distribute builds to build systems that implement `https://github.com/bazelbuild/remote-apis`. Please inspect the `example.yml` file to get familiar with its schema.
During the development process, we use the Buildgrid implementation `https://gitlab.com/BuildGrid/buildgrid` of the REAPI server.

## Setup

Install python3 libraries from the `requirements.txt` file by running `pip install -r requirements.txt`.

Before building, you need to configure the server, port and the project build catalog (explained in the next section) in the `config.ini` file. An example `config.ini.example` file is in the root of the repository.


## Usage

As of now, the user needs to remain in the root of this repository, therefore the project should be copied therein.

After ensuring that the previous steps has succeed, generate the YAML file by running `cmake <dir> -G "Ninja" | ./tools/dep2yaml/dep2yaml.py > out.yml` (where `<dir>` is the catalog containing your project).

Now that the prerequisite files are ready, the execution looks as follows: `./raclient.py <dependencies yml file> target`.
