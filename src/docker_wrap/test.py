#!/usr/local/bin/python3.6

import asyncio
import errno
import os
import signal
import struct
import sys
import socket

import docker
from docker.models.containers import Container

from asyncio.streams import StreamWriter, StreamReader, FlowControlMixin


async def std_io(loop=None):
    if loop is None:
        loop = asyncio.get_event_loop()
    reader = asyncio.StreamReader()
    reader_protocol = asyncio.StreamReaderProtocol(reader)
    writer_transport, writer_protocol = await loop.connect_write_pipe(FlowControlMixin, os.fdopen(1, 'wb'))
    writer = StreamWriter(writer_transport, writer_protocol, None, loop)
    await loop.connect_read_pipe(lambda: reader_protocol, sys.stdin)
    return reader, writer


async def socket_io(sock: socket.socket, loop: asyncio.BaseEventLoop = None):
    if loop is None:
        loop = asyncio.get_event_loop()

    reader = asyncio.StreamReader()
    reader_protocol = asyncio.StreamReaderProtocol(reader, loop=loop)
    writer_transport, writer_protocol = await loop.connect_accepted_socket(reader_protocol, sock=sock)
    writer = StreamWriter(writer_transport, writer_protocol, None, loop)

    return reader, writer


loop = asyncio.get_event_loop()


async def main():
    client = docker.client.from_env()
    container = client.containers.get("test")  # type: Container

    tty = False

    _, socketio = container.exec_run("/bin/bash", stdin=True, socket=True, tty=tty)

    sock = socketio._sock  # type: socket.socket

    std_reader, std_writer = await std_io(loop)
    socket_reader, socket_writer = await std_io(loop)

    async def std_to_socket():
        while True:
            data = await std_reader.readline()
            socket_writer.write(data)

    async def socket_to_std():
        while True:
            data = await socket_reader.readline()
            std_writer.write(data)

    loop.create_task(std_to_socket())
    loop.create_task(socket_to_std())

    # Wait until closing
    while True:
        await asyncio.sleep(1)
        if socket_writer.transport.is_closing() or std_writer.transport.is_closing():
            return


loop.run_until_complete(main())
