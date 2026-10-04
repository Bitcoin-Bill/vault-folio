"""Atomic encrypted-only export; never writes a plaintext guide to disk."""
import json
import os
from pathlib import Path
import tempfile


def save_encrypted(path, envelope, max_bytes=10*1024*1024):
    encoded=json.dumps(envelope,indent=2).encode('utf-8')
    if len(encoded)>max_bytes:
        raise ValueError('Encrypted guide exceeds the reader size limit.')
    target=Path(path)
    fd, temporary=tempfile.mkstemp(prefix='.csip-sealed-',suffix='.tmp',dir=target.parent)
    try:
        with os.fdopen(fd,'wb') as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary,target)
        # Directory durability is best-effort on filesystems without directory fsync.
        try:
            directory=os.open(target.parent,os.O_RDONLY | getattr(os,'O_DIRECTORY',0))
            try:os.fsync(directory)
            finally:os.close(directory)
        except OSError:
            pass
    finally:
        try:os.unlink(temporary)
        except FileNotFoundError:pass
