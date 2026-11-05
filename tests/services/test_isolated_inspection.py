import sys

from pristine.outcomes import Checked, Unchecked
from pristine.services.isolated_inspection import LOST_FILE_REASON, inspect_in_workers

CRASHING_WORKER = (
    "import os, pickle, sys\n"
    "from pristine.outcomes import Checked\n"
    "for path in sys.stdin.buffer.read().decode().split('\\0'):\n"
    "    if path == 'crash.py':\n"
    "        os.abort()\n"
    "    sys.stdout.write(pickle.dumps((path, Checked([]))).hex() + '\\n')\n"
    "    sys.stdout.flush()\n"
)


def test_a_crashing_file_is_unchecked_and_the_others_still_run() -> None:
    paths = ["a.py", "crash.py", "b.py"]
    outcomes = inspect_in_workers(paths, command=(sys.executable, "-c", CRASHING_WORKER))
    assert outcomes == {"a.py": Checked([]), "crash.py": Unchecked(LOST_FILE_REASON), "b.py": Checked([])}
