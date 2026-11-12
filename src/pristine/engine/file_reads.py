import os
import sys
from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass
from types import FrameType

from pristine.engine.read_digests import link_signature
from pristine.reports.outcomes import Signature

READ_EVENTS = frozenset({"open"})
LIST_EVENTS = frozenset({"os.listdir", "os.scandir"})
IMPORT_MACHINERY = "<frozen importlib"
CURRENT_DIRECTORY = "."

type StatFunction = Callable[..., os.stat_result]
type Accesses = dict[str, Access]


@dataclass
class Access:
    listed: bool
    signature: Signature | None


def is_importing(frame: FrameType | None) -> bool:
    while frame is not None:
        if frame.f_code.co_filename.startswith(IMPORT_MACHINERY):
            return True
        frame = frame.f_back
    return False


def replace_stat_functions(stat: StatFunction, lstat: StatFunction) -> None:
    vars(os).update(stat=stat, lstat=lstat)


class ReadRecorder:
    def __init__(self) -> None:
        self.reads: Accesses | None = None
        self.untraceable = False
        self.hooked = False
        self.lstat: StatFunction = os.lstat

    def audit(self, event: str, arguments: tuple[object, ...]) -> None:
        if self.reads is not None and (event in READ_EVENTS or event in LIST_EVENTS):
            self.note(arguments[0] if arguments else None, listed=event in LIST_EVENTS)

    def note(self, target: object, *, listed: bool) -> None:
        if self.reads is None or is_importing(sys._getframe(2)):
            return
        if target is None:
            target = CURRENT_DIRECTORY
        if not isinstance(target, (str, bytes, os.PathLike)):
            self.untraceable = True
            return
        path = os.path.abspath(os.fsdecode(target))
        access = self.reads.get(path)
        if access is None:
            self.reads[path] = Access(listed, link_signature(path, self.lstat))
        else:
            access.listed = access.listed or listed

    def traced(self, stat: StatFunction) -> StatFunction:
        def observed(target: object, *arguments: object, **options: object) -> os.stat_result:
            self.note(target, listed=False)
            return stat(target, *arguments, **options)

        return observed

    @contextmanager
    def recording(self) -> Generator[Accesses]:
        if not self.hooked:
            sys.addaudithook(self.audit)
            self.hooked = True
        stat, lstat = os.stat, os.lstat
        self.lstat = lstat
        replace_stat_functions(self.traced(stat), self.traced(lstat))
        reads: Accesses = {}
        self.reads, self.untraceable = reads, False
        try:
            yield reads
        finally:
            self.reads = None
            replace_stat_functions(stat, lstat)


RECORDER = ReadRecorder()
