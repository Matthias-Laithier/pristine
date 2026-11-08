import json
import sys

from pristine.engine.inspection import inspect_file
from pristine.reports.outcome_lines import encoded_outcome


def main() -> None:
    for line in sys.stdin:
        path: object = json.loads(line)
        if isinstance(path, str):
            sys.stdout.write(encoded_outcome(path, inspect_file(path)))
            sys.stdout.flush()
        else:
            raise TypeError("worker input must be a JSON string")


if __name__ == "__main__":
    main()
