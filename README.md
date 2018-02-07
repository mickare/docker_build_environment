# Docker-Wrap

**Docker-Wrap** is a command-line tool designed to containerize the local development. It automatically provisions a 
container, mounts the working directory and forwards the build & test commands inside the container.

Devs no longer need to install a ton of dependencies on their machines to match the project's requirements.
The dependencies can be properly defined in a Dockerfile.

Exotic requirements and complex setups can be encapsulated and your devs can start coding directly without worry on
dependency conflicts between projects.

## Installation and documentation

Docker-Wrap is in alpha state and is under heavy work.

//ToDo

## Usage

Docker-Wrap is a small wrapper tool, so you will have to call it with your build command appended.
E.g. instead of calling `make` you call `docker-wrap make`.

By default Docker-Wrap mounts the current directory into the container at `/workdir/`.

//ToDo

### Configuration: docker-wrap.yml
The configuration is heavily inspired by the configuration of [docker-compose](https://docs.docker.com/compose/compose-file/).


### Host

- `host.provision`  
    Commands that are called when the container is created.
    
- `host.before`  
    Commands that are called before the existing container is started. If one of those commands fail the script
    will abort
    
- `host.after`  
    Commands that are called after the container has stopped.
    
- `host.clean`  
    Commands that are called when the container is removed.
   

###### Examples
```
host:
  provision:
    - echo 'host.provision - Called when the container is created.'
  before:
    - echo 'host.before - Called on the host machine before the container is started.'
  after:
    - echo 'host.after - Called on the host machine after the container stopped.'
  clean:
    - echo 'host.clean - Container environment is cleaned.'

```

### Container
- `container.name`  
    The name of the provisioned container. By default the directory name is used as a base.
    
- `container.image`  
    The image to run.
     
- `container.build`  
    The Dockerfile to build and run. `build` is incompatible with `image`.
    - `container.build.path`  
        Path to the Dockerfile
    - `container.build.buildargs`  
        Sets variables to be used during build as [build-args](https://docs.docker.com/engine/reference/commandline/build/#set-build-time-variables-build-arg).
        The environment variables that are defined in `container.environment` are also passed to the build command.
        Use buildargs if you want to specific arguments only during build.
    - `container.build.suffix`  
        The suffix that will be appended to the build image's name.
         
- `container.volumes`  
    The volumes that should be mounted.
    
- `container.ports`  
    Ports to bind inside the container.
    
- `container.networks`  
    List of names of networks this container will be connected to at creation time.
    
- `container.network_mode`  
    One of `bridge`, `none` or `host`. Incompatible with `networks`.
    
- `container.environment`  
    Environment variables to set inside the container, as a dictionary or a list of strings. Environment variables on
    the host machine can used with the `${VAR_NAME}` syntax. If you want to prevent that, use `$${VAR_NAME}`.
  

###### Examples
```
container:
  image: "ubuntu:latest"
  volumes:
    - .:/workdir/:rw
  network_mode: host
  environment:
    - "ENV_VARIABLE=content"
    - "HOST_USER=${USER}"
```

```
container:
  name: MyBuildContainer
  build: .
  volumes:
    - .:/workdir/:rw 
  ports:
    - 80:80
  networks:
    - some-network
  environment:
    HOST_USER: "${USER}"
```


```
container:
  name: MyBuildContainer
  build:
    path: ./docker/BuildDockerfile
    buildargs:
        - HTTP_PROXY=http://localhost:5542
```




## Contributing
Help to improve Docker-Wrap, by writing issues with bugs, feature requests, etc.

Or go even further and fork the project and start coding yourself. Pull requests are gladly accepted.

## ToDo
- Readme
- Code documentation
- Tests!
- Wiki
- Do ToDo's ToDo