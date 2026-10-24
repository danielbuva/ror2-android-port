"""Exact-SDK shader IPC for owner-side Android Vulkan compilation.

The caller supplies its acquired compiler command (including a GNU user runner
on Android), SDK data directory and private output directory. No Editor/project
or target shader bytes are used. Original DXBC recovery and serialized shader
construction belong to the content producer.
"""

from contextlib import contextmanager
import json
from pathlib import Path
import socket
import struct
import subprocess

MAGIC = 202101220


class Connection:
    def __init__(self, stream):
        self.stream = stream

    def receive(self, length):
        data = bytearray()
        while len(data) < length:
            chunk = self.stream.recv(length - len(data))
            if not chunk:
                raise EOFError("shader compiler closed its stream")
            data.extend(chunk)
        return bytes(data)

    def number(self, bits):
        if struct.unpack("<I", self.receive(4))[0] != MAGIC:
            raise ValueError("shader compiler IPC version differs")
        return struct.unpack("<I" if bits == 32 else "<Q", self.receive(bits // 8))[0]

    def buffer(self):
        length = self.number(64)
        if length > 64 * 1024**2:
            raise ValueError("shader compiler IPC buffer exceeds the qualified limit")
        return self.receive(length)

    def string(self):
        return self.buffer().decode("utf-8")

    def send_number(self, value, bits=32):
        self.stream.sendall(struct.pack("<II" if bits == 32 else "<IQ", MAGIC, value))

    def send_string(self, value):
        data = value.encode("utf-8")
        self.send_number(len(data), 64)
        self.stream.sendall(data)

    def initialize(self, includes, redirects):
        if self.string() != "":
            raise ValueError("unexpected shader compiler startup response")
        self.send_string("c:initializeCompiler")
        self.send_number(len(includes))
        for directory in includes:
            self.send_string(str(directory))
        self.send_number(len(redirects))
        for source, destination in redirects.items():
            self.send_string(source)
            self.send_string(destination)
        self.send_string(json.dumps({}))
        available = self.number(32)
        capabilities = [(self.number(64), self.number(32)) for _ in range(25)]
        if not available & (1 << 18):
            raise ValueError("acquired SDK compiler does not support Vulkan")
        return capabilities

    def compile(self, source, filename, *, stage, platform_keywords=(), keywords=(), disabled_keywords=(), flags=0, requirements=1):
        """Compile an HLSL vertex/fragment snippet; retain reflection/errors."""
        program = {"vertex": 0, "fragment": 1}[stage]
        filename = Path(filename)
        self.send_string("c:compileSnippet")
        for value in (source, str(filename.parent), filename.name, ""):
            self.send_string(value)
        for value in (0, 0, 0, 13, 0):  # preprocessing options, Android, signature
            self.send_number(value)
        for group in (platform_keywords, keywords, disabled_keywords):
            self.send_number(len(group))
            for keyword in group:
                self.send_string(keyword)
        for value in (flags, 0, program, 18):  # HLSL, selected program, Vulkan
            self.send_number(value)
        self.send_number(requirements, 64)
        self.send_number(1 << program)
        self.send_number(1)
        reflection, diagnostics = [], []
        while True:
            message = self.string()
            if message.startswith("shader: "):
                return {
                    "success": message == "shader: 1",
                    "gpu_program_type": self.number(32),
                    "data": self.buffer(),
                    "reflection": reflection,
                    "diagnostics": diagnostics,
                }
            if message.startswith("err: "):
                diagnostics.append({"location": message, "file": self.string(), "message": self.string()})
            else:
                reflection.append(message)


@contextmanager
def compiler(command, sdk_data, output, *, includes=(), redirects=None, env=None, timeout=120):
    """Run only an explicitly supplied compiler; logs stay in owned output."""
    output = Path(output).resolve()
    output.mkdir()
    with socket.socket() as server, (output / "process.log").open("wb") as log:
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        server.settimeout(timeout)
        args = [*map(str, command), str(sdk_data), str(output / "compiler.log"), str(server.getsockname()[1])]
        process = subprocess.Popen(args, stdout=log, stderr=subprocess.STDOUT, env=env)
        stream = None
        try:
            stream, _ = server.accept()
            stream.settimeout(timeout)
            connection = Connection(stream)
            connection.initialize(includes, redirects or {})
            yield connection
        finally:
            if stream:
                try:
                    Connection(stream).send_string("c:shutdown")
                except OSError:
                    pass
                stream.close()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
