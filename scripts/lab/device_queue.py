"""FIFO shared by detached device jobs and the legacy grant dispatcher."""

import argparse
from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import re
import time
from uuid import uuid4


GRANT_SECONDS = 8 * 60
ENABLED = ".self-queue-enabled"


def publish(path, text):
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text)
    temporary.replace(path)


class DeviceQueue:
    def __init__(self, orchestrator, serial):
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", serial):
            raise ValueError("Invalid device queue serial")
        self.directory = Path(orchestrator) / "devqueue"
        self.lease = self.directory.parent / "leases" / serial
        self.queue = self.directory / (serial + ".queue")
        self.cursor = self.directory / (serial + ".cursor")
        self.grant = self.directory / (serial + ".granted")
        self.taken = self.directory / (serial + ".granted.taken")
        self.lock = self.directory / (serial + ".lock")
        self.tickets = self.directory / (serial + ".jobs")

    @contextmanager
    def locked(self):
        self.directory.mkdir(parents=True, exist_ok=True)
        with self.lock.open("a") as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            yield

    def rows(self):
        # Legacy producers append via shell redirection and do not take our
        # lock. Advancing a cursor, instead of rewriting the queue, preserves
        # any append that arrives during a head transition.
        with self.queue.open("a+b") as stream:
            stream.seek(0)
            stat = os.fstat(stream.fileno())
            identity = f"{stat.st_dev}:{stat.st_ino}"
            if self.cursor.exists():
                recorded, offset = self.cursor.read_text().split()
                if recorded == identity and int(offset) <= stat.st_size:
                    stream.seek(int(offset))
            for row in iter(stream.readline, b""):
                if not row.endswith(b"\n"):
                    break
                yield row.decode().strip(), f"{identity} {stream.tell()}\n"

    def job_alive(self, row):
        ticket = self.tickets / row[1:]
        try:
            os.kill(int(ticket.read_text()), 0)
        except (FileNotFoundError, ProcessLookupError):
            ticket.unlink(missing_ok=True)
            return False
        return True

    def head(self):
        for row, cursor in self.rows():
            if re.fullmatch(r"[a-z0-9-]+", row):
                return row, cursor
            if re.fullmatch(r"@[0-9a-f]{32}", row) and self.job_alive(row):
                return row, cursor
            publish(self.cursor, cursor)
        return None, None

    def reserved(self):
        if self.lease.exists():
            if self.grant.exists():
                self.taken.touch()
            return True
        if self.grant.exists() and not self.taken.exists() and time.time() - self.grant.stat().st_mtime < GRANT_SECONDS:
            return True
        self.grant.unlink(missing_ok=True)
        self.taken.unlink(missing_ok=True)
        return False

    def grant_legacy(self):
        with self.locked():
            if self.reserved():
                return None
            row, cursor = self.head()
            if row is None or row.startswith("@"):
                return None
            publish(self.grant, row + "\n")
            publish(self.cursor, cursor)
            return row

    def wait(self, acquire):
        if not (self.directory / ENABLED).is_file():
            raise RuntimeError("Device dispatcher has not enabled self-queue")
        token = uuid4().hex
        ticket = self.tickets / token
        try:
            with self.locked():
                self.tickets.mkdir(exist_ok=True)
                ticket.write_text(str(os.getpid()))
                with self.queue.open("ab") as stream:
                    stream.write(f"@{token}\n".encode())
            while True:
                with self.locked():
                    if not self.reserved():
                        row, cursor = self.head()
                        if row == "@" + token:
                            try:
                                acquire()
                            except FileExistsError:
                                pass  # An existing non-queued lease owner won mkdir.
                            else:
                                publish(self.cursor, cursor)
                                return
                time.sleep(1)
        finally:
            ticket.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dispatch", type=Path, required=True, metavar="ORCHESTRATOR_DIR")
    args = parser.parse_args()
    directory = args.dispatch / "devqueue"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / ENABLED).touch()
    serials = {path.stem for suffix in ("*.queue", "*.granted") for path in directory.glob(suffix)}
    for serial in sorted(serials):
        workstream = DeviceQueue(args.dispatch, serial).grant_legacy()
        if workstream:
            print(serial, workstream)


if __name__ == "__main__":
    main()
