# Docker Build Environment


DBuild is a command-line tool for running build steps inside a Docker container locally.  It brings the benefits of
containerization to the local dev-machine, with no need of a complex and big CI-pipeline (Continous Integration). 

Choose an existing Docker image, or build from a Dockerfile. DBuild will automatically provision a container and mount
your project's working directory. Your build commands are executed inside the container.

Here are some reasons for dockerizing the build environment:
- A clean dev-machine:
  - Dependencies are installed inside of a container
- A well-defined build environment and dependencies
  - Same environment for all developers
  - Exotic and complex setups are containerized (e.g. environment variables in TensorFlow, etc)
- No dependency conflicts between projects

//ToDo

## Installation and documentation

DBuild is in alpha state and is under heavy work.

//ToDo

## Contributing
Help to improve DBuild, by writing issues with bugs, feature requests, etc.

Or go even further and fork the project and start coding yourself. Pull requests are gladly accepted.

//ToDo

## Usage

DBuild is a small wrapper tool, so you will have to call DBuild with your build command.
E.g. instead of calling `make` you call `dbuild make`.

By default DBuild mounts the current directory into the container at `/workdir/`.

//ToDo

## ToDo
- Readme
- Code documentation
- Tests!
- Wiki
- Do ToDo's ToDo