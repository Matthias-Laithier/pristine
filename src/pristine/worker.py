import pickle
import sys

from pristine.inspection import inspect_file


def main() -> None:
    for path in sys.stdin.buffer.read().decode().split("\0"):
        if not path:
            continue
        sys.stdout.write(pickle.dumps((path, inspect_file(path))).hex() + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
