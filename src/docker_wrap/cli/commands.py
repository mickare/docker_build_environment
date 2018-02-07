import argparse
from typing import Dict

from docker_wrap.context import DContext


class Command:
    def __init__(self, name: str, help: str):
        """
        Base command initialization.
        :param name: Name of command
        :param help:  Help text of command
        """
        self.name = name
        self.help = help
        self.parser = None

    def _initSubParser(self, subparsers, parser_args=None):
        """
        Initialize the subparser for this command. This is only called by the CommandManager and you should not call it.
        :param subparsers:
        :param parser_args:
        :return:
        """
        assert self.parser is None
        if parser_args is None:
            self.parser = subparsers.add_parser(self.name, help=self.help)
        else:
            self.parser = subparsers.add_parser(self.name, help=self.help, **parser_args)
        self.add_arguments(parser=self.parser)

    def add_arguments(self, parser: argparse.ArgumentParser):
        """
        Overwrite this.
        Adds the required arguments for this command to the supplied parser.
        :param parser: Parser that should handle the arguments.
        :return:
        """
        pass

    def run(self, context: DContext, args):
        """
        Overwrite this.
        Runs the command with the
        :param context:
        :param args:
        :return:
        """
        raise NotImplementedError()


class CommandManager:

    def __init__(self, parser: argparse.ArgumentParser):
        self.parser = parser
        self.subparsers = parser.add_subparsers(dest="command")
        self.commands = dict()  # type: Dict[str, Command]

    def registerCommand(self, command: Command, parser_args: Dict = None):
        self.commands[command.name] = command
        command._initSubParser(subparsers=self.subparsers, parser_args=parser_args)

    def getCommand(self, name: str) -> Command:
        return self.commands[name]

    def run(self, context: DContext, args):
        assert args.command in self.commands  # Unknown command, although defined in arparser command list!
        self.getCommand(name=args.command).run(context=context, args=args)


class CleanCommand(Command):

    def __init__(self):
        super(CleanCommand, self).__init__(name="clean", help="Clean the build environment")

    def add_arguments(self, parser: argparse.ArgumentParser):
        pass

    def run(self, context: DContext, args):
        context.clean()


class RunCommand(Command):
    def __init__(self):
        super(RunCommand, self).__init__(name="run", help="Run a command in the build container")

    def add_arguments(self, parser: argparse.ArgumentParser):
        parser.add_argument("--workdir", help="Change the working directory")
        parser.add_argument("--user", help="Set the user running the command")
        parser.add_argument("--env", "-e", action='append', help="Adds a environment variable in the container")
        parser.add_argument("cmd", help="Command to be executed in the container")
        parser.add_argument("cmd_args", nargs=argparse.REMAINDER, help="Arguments for the command")

    def run(self, context: DContext, args):
        user = args.user if args.user else ''
        workdir = args.workdir if args.workdir else context.get_default_workdir()
        user = args.user if args.user else context.get_current_user()
        environment = dict()  # type: Dict[str, str]
        if args.env:
            for e in args.env:
                spl = e.split("=", maxsplit=1)
                assert len(spl) == 2
                assert len(spl[0]) > 0
                environment[spl[0]] = spl[1]

        cmd = [args.cmd]
        if args.cmd_args:
            cmd.extend(args.cmd_args)
        context.execute(cmd=cmd, workdir=workdir, user=user, environment=environment)
