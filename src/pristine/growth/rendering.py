import json

from pristine.growth.account import Growth, Kind

__all__ = ["render_growth_json", "render_growth_text"]

MAINTAINED = (Kind.CODE, Kind.TESTS, Kind.OTHER)
NEXT_STEP = (
    "next: complete the CR-20 subtraction pass on the affected paths, then report these counts, what the pass "
    "removed, and the requirement behind every new mechanism. Tests growing faster than code is a TST-3 signal."
)


def net(growth: Growth, kind: Kind) -> int:
    return growth.added[kind] - growth.removed[kind]


def render_growth_text(growth: Growth) -> str:
    lines = [f"Growth since {growth.base}"]
    lines += [f"{kind}: +{growth.added[kind]} -{growth.removed[kind]} (net {net(growth, kind):+d})" for kind in Kind]
    maintained = sum(net(growth, kind) for kind in MAINTAINED)
    lines.append(f"maintained lines: net {maintained:+d}, generated and lockfiles excluded")
    lines.append(f"files: {growth.files_added} added, {growth.files_removed} removed")
    lines += ["", NEXT_STEP]
    return "\n".join(lines)


def render_growth_json(growth: Growth) -> str:
    kinds = {kind: {"added": growth.added[kind], "removed": growth.removed[kind]} for kind in Kind}
    document = {
        "base": growth.base,
        "lines": kinds,
        "maintained_net": sum(net(growth, kind) for kind in MAINTAINED),
        "files_added": growth.files_added,
        "files_removed": growth.files_removed,
        "next_step": NEXT_STEP,
    }
    return json.dumps(document, indent=2)
