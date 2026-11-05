import sys

from pristine.inspection import inspect_file
from pristine.outcome_lines import encoded_outcome


def main() -> None:
    for path in sys.stdin.buffer.read().decode().split("\0"):
        if not path:
            continue
        sys.stdout.write(encoded_outcome(path, inspect_file(path)))
        sys.stdout.flush()


if __name__ == "__main__":
    main()
