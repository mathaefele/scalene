import mmap
import os
import socket
import sys
from typing import Any, NewType, TextIO

if sys.platform != "win32":
    from scalene import get_line_atomic  # type: ignore

Filename = NewType("Filename", str)


class ScaleneMapFile:

    # Things that need to be in sync with the C++ side
    # (see include/sampleheap.hpp, include/samplefile.hpp)

    MAX_BUFSIZE = 256  # Must match SampleFile::MAX_BUFSIZE

    def __init__(self, name: str) -> None:
        self._name = name
        self._buf = bytearray(ScaleneMapFile.MAX_BUFSIZE)
        #   file to communicate samples (+ PID)
        no_clash_hash = str(os.getuid())
        self._signal_filename = Filename(
            f"/tmp/scalene-{name}-signal{os.getpid()}-{no_clash_hash}"
        )
        self._lock_filename = Filename(
            f"/tmp/scalene-{name}-lock{os.getpid()}-{no_clash_hash}"
        )
        self._init_filename = Filename(
            f"/tmp/scalene-{name}-init{os.getpid()}-{no_clash_hash}"
        )
        self._signal_position = 0
        self._lastpos = bytearray(8)
        self._signal_mmap = None
        self._lock_mmap: mmap.mmap
        self._signal_fd: TextIO
        self._lock_fd: TextIO
        self._signal_fd = open(self._signal_filename, "r")
        os.unlink(self._signal_fd.name)
        self._lock_fd = open(self._lock_filename, "r+")
        os.unlink(self._lock_fd.name)
        self._signal_mmap = mmap.mmap(
            self._signal_fd.fileno(),
            0,
            mmap.MAP_SHARED,
            mmap.PROT_READ,
        )
        self._lock_mmap = mmap.mmap(
            self._lock_fd.fileno(),
            0,
            mmap.MAP_SHARED,
            mmap.PROT_READ | mmap.PROT_WRITE,
        )

    def close(self) -> None:
        """Close the map file."""
        self._signal_fd.close()
        self._lock_fd.close()

    def cleanup(self) -> None:
        """Remove all map files."""
        try:
            pid = os.getpid()
            for i in range(30):
                fname = self._init_filename.replace(str(pid), str(pid+i))
                if (os.path.isfile(fname)):
                    os.remove(fname)
                fname = self._signal_filename.replace(str(pid), str(pid+i))
                if (os.path.isfile(fname)):
                    os.remove(fname)
        except FileNotFoundError:
            pass

    def read(self) -> Any:
        """Read a line from the map file."""
        if sys.platform == "win32":
            return False
        if not self._signal_mmap:
            return False
        return get_line_atomic.get_line_atomic(
            self._lock_mmap, self._signal_mmap, self._buf, self._lastpos
        )

    def get_str(self) -> str:
        """Get the string from the buffer."""
        map_str = self._buf.rstrip(b"\x00").split(b"\n")[0].decode("ascii")
        return map_str
