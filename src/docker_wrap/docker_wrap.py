#!/usr/local/bin/python3.6

import asyncio
import errno
import os
import signal
import socket
import struct
import sys

import docker
from docker.models.containers import Container


class DockerTerminal:
    recoverable_errors = (errno.EINTR, errno.EDEADLK, errno.EWOULDBLOCK)
    _reader = None
    _writer = None

    def __init__(self, loop: asyncio.BaseEventLoop, sock: socket.socket, tty=False):
        assert not tty or os.isatty(sys.stdout.fileno())
        self._loop = loop
        self._sock = sock
        self._tty = tty
        self._closed = False

    async def start(self, limit=None):
        def factory():
            reader = asyncio.StreamReader(limit=limit, loop=self._loop)
            protocol = asyncio.StreamReaderProtocol(reader, self.__connected, loop=self._loop)
            return protocol

        await self._loop.connect_accepted_socket(protocol_factory=factory, sock=self._sock)

    def __connected(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self._reader = reader
        self._writer = writer
        self._loop.create_task(self.__read())

    async def __read_frame_header(self):
        data = await self._reader.read(8)
        if len(data) != 8:
            return None, -1  # End
        stream_type, actual = struct.unpack('>BxxxL', data)
        return stream_type, actual

    async def __read(self, n=4096):
        if self._tty:
            tty_file = os.ttyname(sys.stdout.fileno)
            while not self._closed:
                data = await self._reader.read(n)
                with open(tty_file, mode='w') as fd_out:
                    fd_out.write(data)
        else:
            # With Header
            # see: https://docs.docker.com/engine/api/v1.35/#operation/ContainerAttach
            while not self._closed:
                stream_type, n = await self.__read_frame_header()
                data = await self._reader.read(n)
                if stream_type == 0:  # stdin
                    # ignore
                    pass
                elif stream_type == 1:  # stdout
                    print(data)
                elif stream_type == 2:  # stderr
                    print(data, file=sys.stderr)
                else:
                    raise RuntimeError("unexpected stream type %s" % stream_type)

    def write(self, data):
        if self._tty:
            self._writer.write(data)
        else:
            # With Header
            # see: https://docs.docker.com/engine/api/v1.35/#operation/ContainerAttach
            buf = struct.pack('>BxxxL', 0, data)
            self._writer.write(buf)

    async def drain(self):
        await self._writer.drain()


def main():
    client = docker.client.from_env()
    container = client.containers.get("test")  # type: Container

    loop = asyncio.SelectorEventLoop()
    exit_future = loop.create_future()

    def close():
        exit_future.set_result(None)

    signal.signal(signal.SIGTERM, close)
    signal.signal(signal.SIGINT, close)

    tty = False

    async def run():
        _, sock = container.exec_run("/bin/bash", stdin=True, socket=True, stream=True, tty=tty)
        term = DockerTerminal(loop, sock, tty=tty)
        await loop.create_task(term.start())
        with open(sys.stdin) as fd_stdin:
            def forward_stdin():
                buf_in = fd_stdin.read(4096)
                term.write(buf_in)

            loop.add_reader(sys.stdin, forward_stdin)

    loop.create_task(run())
    loop.run_until_complete(exit_future)


main()

"""
class DockerTTYStreamPipe:
    _reader = None
    _writer = None

    def __init__(self, loop: asyncio.BaseEventLoop, sock: socket.socket):
        assert sys.stdout.isatty()  # TTY pipe only possible in a real terminal.
        self._loop = loop
        self._sock = sock
        self.close_future = loop.create_future()  # type: asyncio.Future
        self._started = False
        self._closed = False
        self.__prepare_start()

    def __prepare_start(self):
        assert not self._closed
        if not self._started:
            self._started = True
            self._loop.create_task(self.__run)

    def __on_std_in(self):
        for line in sys.stdin:
            self._writer.write(line)

    async def __handle_sock_in(self):
        with open(os.ttyname(sys.stdout.fileno())) as f:
            while not self.close_future.done() and not self._reader.at_eof():
                buffer = await self._reader.read(32)
                if buffer:
                    f.write(buffer)

    def __connected_callback(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        assert self._reader is None
        assert self._writer is None
        self._reader = reader
        self._writer = writer
        self._loop.create_task(self.__handle_sock_in)
        self._loop.add_reader(sys.stdin, self.__on_std_in)

    def __protocol_factory(self):
        reader = asyncio.StreamReader(loop=self._loop)
        return asyncio.StreamReaderProtocol(reader, self.__connected_callback, self._loop)

    async def __run(self):
        await self._loop.connect_accepted_socket(self.__protocol_factory, sock=self._sock)

    def close(self):
        if self._started and not self._closed:
            self._closed = True
            self._loop.remove_reader(sys.stdin)
            self.close_future.set_result(None)


client = docker.client.from_env()
container = client.containers.get("test")  # type: Container

loop = asyncio.SelectorEventLoop()

exit_code, sock = container.exec_run("/bin/bash", stdin=True, socket=True, tty=True)
pipe = DockerTTYStreamPipe(loop, sock)
loop.run_until_complete(pipe.close_future)
pipe.close()
"""
