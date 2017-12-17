import argparse
import os
import signal

import docker
import yaml

from dbuild.config.config import Config
from dbuild.denvironment import BuildEnvironment, getOrCreateImage


def main():
    parser = argparse.ArgumentParser(
        description=""
    )
    parser.add_argument(
        "--config", "-c",
        dest="config",
        help="use a config, other than the default './dbuild.cfg'",
        type=str
    )
    subparsers = parser.add_subparsers(dest="command")

    parser_clean = subparsers.add_parser("clean", help="Clean the build environment")

    parser_run = subparsers.add_parser("run", help="Run a command in the build container")
    parser_run.add_argument("--workdir", help="Change the working directory")
    parser_run.add_argument("--user", help="Set the user running the command")
    parser_run.add_argument("--env", "-e", action='append', help="Adds a environment variable in the container")
    parser_run.add_argument("cmd", nargs="+", help="Command and arguments to be executed in the container")

    args = parser.parse_args()

    print(args)

    # Default config
    config_defaults = {
        "container": {
            "name": None,
            "build": {
                "path": ".",
                "dockerfile": "Dockerfile",
                "network_mode": "host"
            },
            "workdir": "/workdir/",
            "image": None,
            "network": "host",
            "volumes": {
                ".": {
                    "bind": "/workdir/",
                    "mode": "rw"
                }
            }
        },
        "docker": {}
    }

    config = Config(values=config_defaults)

    config_file = "dbuild.cfg"
    if args.config:
        config_file = args.config

    # Read config
    if os.path.isfile(config_file):
        with open(file=config_file, mode='r') as fc:
            config.update(yaml.load(fc))


    # Prepare config special default
    if "container.name" not in config or config["container.name"] is None:
        config["container.name"] = os.path.basename(os.getcwd())
    assert len(config["container.name"]) > 0

    print(config)

    client = None
    if "docker" in config:
        section = config["docker"]
        assert isinstance(section, dict)
        if len(section) > 0:
            client = docker.DockerClient(**section)
    if client is None:
        client = docker.DockerClient.from_env()

    workdir = config.get(["container", "workdir"], "/workdir/")
    if args.workdir:
        workdir = args.workdir

    app = BuildEnvironment(
        client=client,
        image=lambda: getOrCreateImage(client=client, config=config),
        name=config["container.name"],
        volumes=config.get(["container", "volumes"], {}),
        workdir=workdir
    )
    signal.signal(signal.SIGINT, app.exitGracefully)
    signal.signal(signal.SIGTERM, app.exitGracefully)
    print(args.cmd)
    app.start()
    app.runCommand(cmd=["bash", "-c", "cd " + workdir + " && " + args.cmd])
    # app.runCommand(cmd=args.cmd)
    app.stop()
