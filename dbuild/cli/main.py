import argparse
import os
import signal

import docker
import errno
import yaml

from dbuild.cli.commands import CommandManager, CleanCommand, RunCommand
from dbuild.config.config import Config
from dbuild.dcontext import DContext
from dbuild.denvironment import BuildHandler


def loadConfig(args):
    # Default config
    config = Config(values={
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
    })
    # Load config file
    config_file = "dbuild.cfg"
    if args.config:
        config_file = args.config
        if not os.path.isfile(config_file):
            raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), config_file)

    if os.path.isfile(config_file):
        with open(file=config_file, mode='r') as fc:
            config.update(yaml.load(fc))

    # Prepare config special default
    if "container.name" not in config or config["container.name"] is None:
        config["container.name"] = os.path.basename(os.getcwd())
    assert len(config["container.name"]) > 0

    return config


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

    commandManager = CommandManager(parser=parser)
    commandManager.registerCommand(CleanCommand())
    commandManager.registerCommand(RunCommand())

    args = parser.parse_args()

    context = DContext(config=loadConfig(args))

    signal.signal(signal.SIGINT, context.exitGracefully)
    signal.signal(signal.SIGTERM, context.exitGracefully)

    commandManager.run(context, args)


