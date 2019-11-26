# Remote Execution API Client

## Setup

Install python3 libraries from requirements.txt file.

Configure server file and port in config.ini file. There is an example config.ini.example file.

Execute: `./raclient.py <dependencies yml file> target`

## Usage

REAPI CLient uses project dependencies descrbed in yaml file to distribute builds to buildsystems that implement `https://github.com/bazelbuild/remote-apis`. Inspect example.yml file to familiarize with its schema. 
During development we use Buildgrid implementation `https://gitlab.com/BuildGrid/buildgrid`.


