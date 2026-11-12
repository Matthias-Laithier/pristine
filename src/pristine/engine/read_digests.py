import hashlib
import os
import stat
from collections.abc import Callable

from pristine.reports.outcomes import FileRead, Signature

ABSENT = "absent"
UNREADABLE = "unreadable"


def signature_of(metadata: os.stat_result) -> Signature:
    return (metadata.st_dev, metadata.st_ino, metadata.st_size, metadata.st_mtime_ns, metadata.st_ctime_ns)


def file_signature(path: str) -> Signature | None:
    try:
        return signature_of(os.stat(path))
    except OSError:
        return None


def link_signature(path: str, lstat: Callable[[str], os.stat_result] = os.lstat) -> Signature | None:
    try:
        return signature_of(lstat(path))
    except OSError:
        return None


def listing_digest(path: str) -> str:
    names = "\0".join(sorted(os.listdir(path)))
    return hashlib.sha256(os.fsencode(names)).hexdigest()


def target_digest(path: str, *, listed: bool) -> str:
    metadata = os.stat(path)
    if stat.S_ISREG(metadata.st_mode):
        with open(path, "rb") as source:
            return "file:" + hashlib.file_digest(source, "sha256").hexdigest()
    if stat.S_ISDIR(metadata.st_mode):
        return "directory:" + listing_digest(path) if listed else "directory"
    return "other"


def read_digest(path: str, *, listed: bool) -> str:
    try:
        link = os.lstat(path)
    except FileNotFoundError, NotADirectoryError:
        return ABSENT
    except OSError:
        return UNREADABLE
    try:
        prefix = "link:" + os.readlink(path) + "|" if stat.S_ISLNK(link.st_mode) else ""
        return prefix + target_digest(path, listed=listed)
    except FileNotFoundError, NotADirectoryError:
        return ABSENT
    except OSError:
        return UNREADABLE


def observed_read(path: str, *, listed: bool, signature: Signature | None) -> FileRead:
    return FileRead(listed, read_digest(path, listed=listed), signature)
