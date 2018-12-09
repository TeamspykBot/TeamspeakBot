# coding=utf-8
import socket
import os
import struct
import select
from threading import Thread
import threading


class UnixServer(Thread):
    def __init__(self, queue, socket_path):
        super().__init__()

        self.queue = queue

        self.socket_path = socket_path

        self.shutdown_flag = threading.Event()

        if os.path.exists(self.socket_path):
            os.remove(self.socket_path)

        self.server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server.bind(self.socket_path)
        os.chmod(self.socket_path, 666)
        self.client = None

    def recv_exact(self, length):
        data = b""
        while len(data) < length:
            ret = self.client.recv(length)
            if ret == b"":
                return None
            data += ret
        return data

    def kill(self):
        self.shutdown_flag.set()

    def run(self):
        self.server.listen(1)

        while not self.shutdown_flag.is_set():
            readable, writable, errored = select.select([self.server], [], [], 0)
            if len(readable) > 0:
                self.client, _ = self.server.accept()
                break

        while not self.shutdown_flag.is_set():
            datagram = self.recv_exact(4)
            if datagram is None:
                break
            else:
                sender, length = struct.unpack("<HH", datagram)

                data = self.recv_exact(length)
                self.queue.put_nowait([sender, data])

        self.cleanup()

    def cleanup(self):
        if self.client is not None:
            self.client.close()
        self.server.close()
        os.remove(self.socket_path)

