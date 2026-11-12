import hashlib
import hmac
import json
from collections.abc import Iterator
from contextlib import suppress
from pathlib import Path

from pristine.reports.outcome_lines import decoded_body, outcome_record
from pristine.reports.outcomes import Checked, Outcome, Skipped, Unsupported
from pristine.services.outcome_cache.files import read_limited, write_atomically
from pristine.services.outcome_cache.inputs import FileInputs

CACHEABLE = (Checked, Skipped, Unsupported)
SEAL_SEPARATOR = b"\n"
ENTRY_LIMIT = 200_000

type Entries = dict[str, dict[str, object]]


def valid_outcome(entry: object, path: str, key: str) -> Outcome | None:
    if not isinstance(entry, dict) or entry.get("key") != key:
        return None
    try:
        outcome = decoded_body(entry)
    except ValueError:
        return None
    if not isinstance(outcome, CACHEABLE):
        return None
    if isinstance(outcome, Checked) and any(finding.path != path for finding in outcome.findings):
        return None
    return outcome


class OutcomeCache:
    def __init__(self, location: Path, inputs: FileInputs, secret: bytes) -> None:
        self.location = location
        self.inputs = inputs
        self.secret = secret
        self.stored: Entries = {}
        self.fresh: Entries = {}
        self.keys: dict[str, str] = {}

    def seal(self, payload: bytes) -> bytes:
        return hmac.digest(self.secret, payload, hashlib.sha256).hex().encode()

    def load(self) -> Entries:
        data = read_limited(self.location)
        seal, separator, payload = (b"", b"", b"") if data is None else data.partition(SEAL_SEPARATOR)
        if not separator or not hmac.compare_digest(seal, self.seal(payload)):
            return {}
        try:
            document = json.loads(payload)
        except ValueError:
            return {}
        if not isinstance(document, dict):
            return {}
        return {path: entry for path, entry in document.items() if isinstance(path, str) and isinstance(entry, dict)}

    def lookup(self, paths: list[str]) -> tuple[dict[str, Outcome], list[str]]:
        self.stored = self.load()
        hits: dict[str, Outcome] = {}
        misses = []
        for path in paths:
            key = self.inputs.key(path)
            if key is None:
                misses.append(path)
                continue
            self.keys[path] = key
            outcome = valid_outcome(self.stored.get(path), path, key)
            if outcome is None:
                misses.append(path)
            else:
                hits[path] = outcome
                self.fresh[path] = self.stored[path]
        return hits, misses

    def recorded(self, outcomes: Iterator[tuple[str, Outcome]]) -> Iterator[tuple[str, Outcome]]:
        for path, outcome in outcomes:
            key = self.keys.get(path)
            if key is not None and isinstance(outcome, CACHEABLE):
                self.fresh[path] = {"key": key, **outcome_record(outcome)}
            yield path, outcome
        self.save()

    def save(self) -> None:
        changed = self.inputs.changed_paths(self.fresh)
        kept = {path: entry for path, entry in self.fresh.items() if path not in changed}
        others = (item for item in self.stored.items() if item[0] not in self.keys and self.inputs.exists(item[0]))
        for path, entry in others:
            if len(kept) >= ENTRY_LIMIT:
                break
            kept[path] = entry
        if kept == self.stored:
            return
        payload = json.dumps(kept).encode()
        with suppress(OSError):
            write_atomically(self.location, self.seal(payload) + SEAL_SEPARATOR + payload)
