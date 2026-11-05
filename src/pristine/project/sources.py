from dataclasses import dataclass, field
from pathlib import Path

ENCODING = "utf-8"


@dataclass
class SourceReader:
    root: Path
    checked: set[str] = field(default_factory=set)
    unchecked: dict[str, str] = field(default_factory=dict)

    def text(self, relative: str) -> str | None:
        try:
            content = (self.root / relative).read_text(encoding=ENCODING)
        except (OSError, UnicodeDecodeError) as error:
            self.unchecked[relative] = f"unreadable: {error}"
            return None
        self.checked.add(relative)
        return content

    def reject(self, relative: str, reason: str) -> None:
        self.checked.discard(relative)
        self.unchecked[relative] = reason

    def is_local_file(self, relative: str) -> bool:
        candidate = (self.root / relative).resolve()
        return candidate.is_relative_to(self.root.resolve()) and candidate.is_file()
