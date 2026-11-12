import os
import secrets
import stat
from contextlib import suppress
from pathlib import Path

IGNORE_FILE = ".gitignore"
IGNORE_EVERYTHING = b"*\n"
STORE_PREFIX = "outcomes-"
STORE_LIMIT_IN_BYTES = 256 * 1024 * 1024
KEPT_OTHER_STORES = 3
SECRET_BYTES = 32
TEMPORARY_SUFFIX = ".tmp"
READ_FLAGS = os.O_RDONLY | os.O_NOFOLLOW
WRITE_FLAGS = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
ENTRY_MODE = 0o644
SECRET_MODE = 0o600
FOREIGN_ACCESS_BITS = 0o077


def owned_directory(path: Path) -> None:
    metadata = os.lstat(path)
    if not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid != os.getuid():
        raise OSError(f"{path} is not a directory owned by this user")


def temporary_beside(target: Path) -> Path:
    return target.with_name(f".{target.name}.{os.getpid()}.{secrets.token_hex(4)}{TEMPORARY_SUFFIX}")


def written_temporary(target: Path, data: bytes, mode: int) -> Path:
    temporary = temporary_beside(target)
    descriptor = os.open(temporary, WRITE_FLAGS, mode)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(data)
    except BaseException:
        with suppress(OSError):
            os.unlink(temporary)
        raise
    return temporary


def write_atomically(target: Path, data: bytes) -> None:
    temporary = written_temporary(target, data, ENTRY_MODE)
    try:
        os.replace(temporary, target)
    except BaseException:
        with suppress(OSError):
            os.unlink(temporary)
        raise


def publish_once(target: Path, data: bytes, mode: int) -> None:
    temporary = written_temporary(target, data, mode)
    try:
        os.link(temporary, target, follow_symlinks=False)
    except FileExistsError:
        pass
    finally:
        with suppress(OSError):
            os.unlink(temporary)


def read_limited(path: Path, limit: int = STORE_LIMIT_IN_BYTES) -> bytes | None:
    try:
        with os.fdopen(os.open(path, READ_FLAGS), "rb") as source:
            metadata = os.fstat(source.fileno())
            is_bounded = stat.S_ISREG(metadata.st_mode) and metadata.st_size <= limit
            return source.read(limit) if is_bounded else None
    except OSError:
        return None


def user_secret(directory: Path) -> bytes:
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    owned_directory(directory)
    path = directory / "outcome-cache.key"
    if not os.path.lexists(path):
        publish_once(path, secrets.token_bytes(SECRET_BYTES), SECRET_MODE)
    metadata = os.lstat(path)
    secret = read_limited(path, SECRET_BYTES)
    is_private = metadata.st_uid == os.getuid() and not metadata.st_mode & FOREIGN_ACCESS_BITS
    if secret is None or len(secret) != SECRET_BYTES or not is_private:
        raise OSError(f"{path} is not a private {SECRET_BYTES}-byte key")
    return secret


def last_used(path: str) -> int:
    try:
        return os.lstat(path).st_mtime_ns
    except OSError:
        return 0


def remove_older_stores(root: Path, kept: str) -> None:
    others: list[str] = []
    with suppress(OSError), os.scandir(root) as entries:
        others = [entry.path for entry in entries if entry.name.startswith(STORE_PREFIX) and entry.name != kept]
    for path in sorted(others, key=last_used, reverse=True)[KEPT_OTHER_STORES:]:
        with suppress(OSError):
            os.unlink(path)


def prepared_store(root: Path, name: str) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    owned_directory(root)
    if not os.path.lexists(root / IGNORE_FILE):
        write_atomically(root / IGNORE_FILE, IGNORE_EVERYTHING)
    if not os.path.lexists(root / name):
        remove_older_stores(root, name)
    return root / name
