import argparse
import os
import signal

import yaml

from docker_wrap.cli.commands import CommandManager, CleanCommand, RunCommand
from docker_wrap.config.config2 import Config
from docker_wrap.context import DContext


def load_config(args):
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
    config_file = "docker-wrap.yml"
    if args.config:
        config_file = args.config

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
        help="use a config, other than the default './docker-wrap.yml'",
        type=str
    )

    cmd_manager = CommandManager(parser=parser)
    cmd_manager.registerCommand(CleanCommand())
    cmd_manager.registerCommand(RunCommand())

    args = parser.parse_args()

    context = DContext(config=load_config(args))

    signal.signal(signal.SIGINT, context.exit_gracefully)
    signal.signal(signal.SIGTERM, context.exit_gracefully)

    cmd_manager.run(context, args)
