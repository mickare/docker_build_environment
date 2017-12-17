import argparse
from typing import Dict


class Command:
    def __init__(self, name: str, help: str):
        self.name = name
        self.help = help
        self.parser = None

    def initSubParser(self, subparsers, parser_args):
        assert self.parser is None
        self.parser = subparsers.add_parser(self.name, help=self.help, **parser_args)
        self.add_arguments(self.parser)

    def add_arguments(self, parser: argparse.ArgumentParser):
        pass

    def run(self, args):
        raise NotImplementedError()


class CommandManager:

    def __init__(self, parser: argparse.ArgumentParser):
        self.parser = parser
        self.subparsers = parser.add_subparsers(dest="command")
        self.commands = dict()  # type: Dict[str, Command]

    def registerCommand(self, command: Command, parser_args: Dict = dict):
        self.commands[command.name] = command
        command.initSubParser(subparsers=self.subparsers, parser_args=parser_args)

    def getCommand(self, name: str) -> Command:
        return self.commands[name]

    def run(self, args):
        assert args.command in self.commands  # Unknown command, although defined in arparser command list!
        self.getCommand(name=args.command).run(args)


class CleanCommand(Command):

    def __init__(self):
        super(CleanCommand, self).__init__(name="clean", help="Clean the build environment")

    def add_arguments(self, parser: argparse.ArgumentParser):
        pass

    def run(self, args):
        pass


class RunCommand(Command):
    def __init__(self):
        super(RunCommand, self).__init__(name="run", help="Run a command in the build container")

    def add_arguments(self, parser: argparse.ArgumentParser):
        parser.add_argument("--workdir", help="Change the working directory")
        parser.add_argument("--user", help="Set the user running the command")
        parser.add_argument("--env", "-e", action='append', help="Adds a environment variable in the container")
        parser.add_argument("cmd", nargs="+", help="Command and arguments to be executed in the container")

    def run(self, args):
        pass
