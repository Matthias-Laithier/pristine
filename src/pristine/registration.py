from collections.abc import Callable, Hashable


def registering[Key: Hashable, Entry](registry: dict[Key, Entry], *keys: Key) -> Callable[[Entry], Entry]:
    def register(entry: Entry) -> Entry:
        duplicates = registry.keys() & set(keys)
        if duplicates:
            raise ValueError(f"duplicate registration for {', '.join(map(str, duplicates))}")
        registry.update(dict.fromkeys(keys, entry))
        return entry

    return register
