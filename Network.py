# coding=utf-8
import socket
import select


class TCPConnection:
    def __init__(self, ip, port):
        self._sock = None
        self.ip = ip
        self.port = port
        self._messageBuffer = b""
        self._connected = False

    def connect(self):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.settimeout(10)
        self._sock.connect((self.ip, self.port))
        self._sock.settimeout(None)
        self._connected = True

    def disconnect(self):
        self._connected = False
        try:
            self._sock.shutdown(socket.SHUT_RDWR)
            self._sock.close()
        except socket.error:
            pass

    def message_available(self):
        self._handle_incoming_messages()
        if b"\n\r" in self._messageBuffer:
            return True
        return False

    def _handle_incoming_messages(self):
        readable, writeable, errored = select.select([self._sock], [], [], 0)
        if len(readable) > 0:
            self._messageBuffer += (self._sock.recv(255))

    def get_next_message(self):
        self._handle_incoming_messages()
        if not self.message_available():
            return ""
        message = self._messageBuffer.partition(b"\n\r")
        self._messageBuffer = message[2]
        return message[0].decode("utf-8")

    def send_message(self, message):
        self._sock.send(message.encode("utf-8"))

    def clear_message_buffer(self):
        self._messageBuffer = b""

    def is_connected(self):
        return self._connected
