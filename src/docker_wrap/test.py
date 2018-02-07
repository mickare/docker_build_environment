#!/usr/local/bin/python3.6 -u

import asyncio
import errno
import os
import signal
import struct
import sys
import socket
from typing import Dict

import docker
from docker.models.containers import Container, ExecResult

from asyncio.streams import StreamWriter, StreamReader, FlowControlMixin


def exec_run(container: Container, cmd, stdout=True, stderr=True, stdin=False, tty=False,
             privileged=False, user='', detach=False, stream=False,
             socket=False, environment=None, workdir=None):
    """
    Copy from docker.models.container.Containers.exec_run(..)
    """
    resp = container.client.api.exec_create(
        container.id, cmd, stdout=stdout, stderr=stderr, stdin=stdin, tty=tty,
        privileged=privileged, user=user, environment=environment,
        workdir=workdir
    )
    exec_output = container.client.api.exec_start(
        resp['Id'], detach=detach, tty=tty, stream=stream, socket=socket
    )
    if socket or stream:
        return resp['Id'], None, exec_output

    return resp['Id'], container.client.api.exec_inspect(resp['Id'])['ExitCode'], exec_output


def get_exit_code(container: Container, exec_id):
    return container.client.api.exec_inspect(exec_id)['ExitCode']


async def std_io(loop=None):
    if loop is None:
        loop = asyncio.get_event_loop()
    reader_in = asyncio.StreamReader()
    reader_protocol = asyncio.StreamReaderProtocol(reader_in)

    writer_out_transport, writer_out_protocol = await loop.connect_write_pipe(
        FlowControlMixin, os.fdopen(1, mode='wb', buffering=0))
    writer_out = StreamWriter(writer_out_transport, writer_out_protocol, None, loop)

    writer_err_transport, writer_err_protocol = await loop.connect_write_pipe(
        FlowControlMixin, os.fdopen(2, mode='wb', buffering=0))
    writer_err = StreamWriter(writer_err_transport, writer_err_protocol, None, loop)

    # await loop.connect_read_pipe(lambda: reader_protocol, sys.stdin)
    await loop.connect_read_pipe(lambda: reader_protocol, os.fdopen(0, 'rb', buffering=0))

    return reader_in, writer_out, writer_err


class CloseStreamProtocol(asyncio.StreamReaderProtocol):
    def __init__(self, close_future: asyncio.Future, *args, **kwargs):
        super(CloseStreamProtocol, self).__init__(*args, **kwargs)
        self._close_future = close_future

    @property
    def close_future(self):
        return self._close_future

    def eof_received(self):
        try:
            if not self._close_future.done():
                self._close_future.set_result(True)
        finally:
            super(CloseStreamProtocol, self).eof_received()

    def connection_lost(self, exc):
        try:
            if not self._close_future.done():
                if exc:
                    self._close_future.set_exception(exc)
                else:
                    self._close_future.set_result(True)
        finally:
            super(CloseStreamProtocol, self).connection_lost(exc)


async def socket_io(sock: socket.socket, close_future: asyncio.Future, loop: asyncio.BaseEventLoop = None):
    if loop is None:
        loop = asyncio.get_event_loop()

    reader = asyncio.StreamReader()
    reader_protocol = CloseStreamProtocol(close_future, reader, loop=loop)
    writer_transport, writer_protocol = await loop.connect_accepted_socket(lambda: reader_protocol, sock=sock)
    writer = StreamWriter(writer_transport, writer_protocol, reader, loop)
    return reader, writer


loop = asyncio.SelectorEventLoop()
exit_code = loop.create_future()


async def main():
    close_future = loop.create_future()

    def close():
        if not close_future.done():
            close_future.set_result(True)

    client = docker.client.from_env()
    container = client.containers.get("test")  # type: Container

    tty = True

    exec_id, _, socketio = exec_run(container, "/bin/bash", stdin=True, socket=True, tty=tty)

    sock = socketio._sock  # type: socket.socket

    std_reader_in, std_writer_out, std_writer_err = await std_io(loop)
    socket_reader, socket_writer = await socket_io(sock, close_future, loop)

    async def std_to_socket():
        while not close_future.done():
            data = await std_reader_in.read(128)
            if not data:
                close()
            print("Debug-Into: " + data.decode("utf8"))
            socket_writer.write(data)

    async def socket_to_std():
        if tty:
            while not close_future.done():
                data = await socket_reader.read(128)
                std_writer_out.write(data)
        else:
            while not close_future.done():
                header = await socket_reader.read(8)
                stream_type, n = struct.unpack('>BxxxL', header)

                data = await socket_reader.read(n)
                if stream_type == 1:
                    std_writer_out.write(data)
                    await std_writer_out.drain()
                elif stream_type == 2:
                    std_writer_err.write(data)
                    await std_writer_err.drain()
                else:
                    raise ValueError("Wrong stream type")

    def handle_close_signal():
        close()

    task_in = loop.create_task(socket_to_std())
    task_out = loop.create_task(std_to_socket())

    loop.add_signal_handler(signal.SIGINT, handle_close_signal)

    async def wait_closed():
        while not close_future.done():
            await asyncio.sleep(1)
            if socket_writer.transport.is_closing() \
                    or std_writer_out.transport.is_closing() \
                    or std_writer_err.transport.is_closing():
                close()
                return

    await wait_closed()
    loop.remove_signal_handler(signal.SIGINT)
    task_in.cancel()
    task_out.cancel()
    std_writer_out.close()
    std_writer_err.close()
    socket_writer.close()

    exit_code.set_result(get_exit_code(container, exec_id))


loop.run_until_complete(main())
exit(exit_code.result())
