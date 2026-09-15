"""Cooperating single-host workers on private local Unix storage, not a distributed lease.

The sidecar is persistent and must never be unlinked/replaced while in use.
Kernel lock ownership, not PID/heartbeat age, decides whether a caller may run.
"""
import asyncio
from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import stat

from app.g5.measurement import require


def _task():
    try:
        return asyncio.current_task()
    except RuntimeError:
        return None


def _identity(info):
    return info.st_dev, info.st_ino


class LocalWorker:
    def __init__(self, database):
        self.pid, self.active, self.owner = os.getpid(), False, None
        self.database = None if str(database) == ":memory:" else Path(database).resolve(strict=True)
        if self.database is not None:
            self.database_identity = _identity(self.database.stat())
            self.lock_path = self.database.with_name(self.database.name + ".worker-lock")
        self.fd = None

    def _storage(self):
        info = self.database.stat()
        parent = self.database.parent.stat()
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1
            and info.st_uid == os.getuid() and not info.st_mode & 0o022
            and _identity(info) == self.database_identity, "Worker database identity changed, unsafe or hard-linked")
        require(parent.st_uid == os.getuid() and not parent.st_mode & 0o022,
                "Worker requires an owner-controlled local directory")

    def check(self):
        require(os.getpid() == self.pid and self.active and self.owner is _task(),
                "Worker ownership missing, inherited or belongs to another task")
        if self.database is not None:
            self._storage()
            info = os.fstat(self.fd)
            current = self.lock_path.lstat()
            require(stat.S_ISREG(current.st_mode) and current.st_nlink == 1
                and _identity(current) == _identity(info), "Worker lock identity changed")

    @contextmanager
    def claim(self):
        require(os.getpid() == self.pid and not self.active, "Worker already active or inherited")
        fd = None
        try:
            if self.database is not None:
                self._storage()
                fd = os.open(self.lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
                info = os.fstat(fd)
                require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1
                    and info.st_uid == os.getuid() and not info.st_mode & 0o077,
                    "Worker lock must be a private regular file")
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError as error:
                    raise ValueError("Another local worker owns this prediction database") from error
            self.fd, self.active, self.owner = fd, True, _task()
            self.check()
            yield self
        finally:
            if fd is not None:
                # Closing, rather than unlinking, preserves the shared lock inode.
                os.close(fd)
            self.fd, self.active, self.owner = None, False, None

    @contextmanager
    def operation(self):
        if self.active:
            self.check()
            yield
        else:
            with self.claim():
                yield
