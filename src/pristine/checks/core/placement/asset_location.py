import re
from pathlib import PurePosixPath

from pristine.checks.definitions import PathCheck
from pristine.files.path_roles import VENDORED_DIRECTORIES, holds_test_material
from pristine.reports.findings import Finding, Severity

CHECK_ID = "STR-7"
ASSET_SUFFIXES = frozenset(
    {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico"}
    | {".woff", ".woff2", ".ttf", ".otf", ".eot", ".mp3", ".wav", ".mp4", ".webm"}
)
ASSET_FOLDER_NAMES = frozenset({"assets", "_assets"})
ASSET_FOLDER_SUFFIX = ".assets"
FRAMEWORK_FOLDER_NAMES = frozenset({"public", "static", "_static", "res", "resources", "wwwroot", "fastlane"})
FRAMEWORK_FOLDER_SUFFIXES = (".xcassets", ".lproj", ".bundle")
TAURI_FOLDER = "src-tauri"
DOCUMENTATION_FOLDER_NAMES = frozenset({"docs", "doc", "documentation", "screenshots"})
DOCUMENTATION_SUFFIXES = frozenset({".md", ".mdx", ".rst", ".adoc"})
GOLDEN_FOLDER_PATTERN = re.compile(r".*(snapshots|goldens)")
BUILD_OUTPUT_FOLDER_NAMES = frozenset({"dist", "build"})
NEXT_APP_FOLDER = "app"
NEXT_APP_FILE_STEMS = re.compile(r"(favicon|icon|apple-icon|opengraph-image|twitter-image)\d*")
EXEMPT_FOLDER_NAMES = (
    FRAMEWORK_FOLDER_NAMES | DOCUMENTATION_FOLDER_NAMES | BUILD_OUTPUT_FOLDER_NAMES | VENDORED_DIRECTORIES
)
MOVE_HINT = "move it into the component's assets/ folder, under a type or feature subfolder"


def is_exempt_folder(name: str) -> bool:
    return (
        name in EXEMPT_FOLDER_NAMES
        or name.startswith(".")
        or name.endswith(FRAMEWORK_FOLDER_SUFFIXES)
        or holds_test_material(name)
        or GOLDEN_FOLDER_PATTERN.fullmatch(name) is not None
    )


def is_asset_folder(name: str) -> bool:
    return name in ASSET_FOLDER_NAMES or name.endswith(ASSET_FOLDER_SUFFIX)


def is_next_app_file(path: PurePosixPath, folders: list[str]) -> bool:
    return NEXT_APP_FOLDER in folders and NEXT_APP_FILE_STEMS.fullmatch(path.stem) is not None


def is_framework_placed(path: PurePosixPath, folders: list[str], documented_folders: set[PurePosixPath]) -> bool:
    return (
        any(is_exempt_folder(name) for name in folders)
        or TAURI_FOLDER in folders
        or is_next_app_file(path, folders)
        or path.parent in documented_folders
    )


def asset_finding(path: str, documented_folders: set[PurePosixPath]) -> Finding | None:
    asset_path = PurePosixPath(path)
    folders = [name.lower() for name in asset_path.parts[:-1]]
    if asset_path.suffix.lower() not in ASSET_SUFFIXES or is_framework_placed(asset_path, folders, documented_folders):
        return None
    if not any(is_asset_folder(name) for name in folders):
        return Finding(
            path,
            1,
            CHECK_ID,
            Severity.ERROR,
            f"static asset sits outside an assets/ folder; {MOVE_HINT}, or out of the repository if it is generated",
        )
    if folders[-1] in ASSET_FOLDER_NAMES:
        return Finding(path, 1, CHECK_ID, Severity.WARNING, f"loose file at the root of assets/; {MOVE_HINT}")
    return None


def documented_folders_of(paths: list[str]) -> set[PurePosixPath]:
    return {
        PurePosixPath(path).parent for path in paths if PurePosixPath(path).suffix.lower() in DOCUMENTATION_SUFFIXES
    }


def check_asset_location(paths: list[str]) -> list[Finding]:
    documented_folders = documented_folders_of(paths)
    return [finding for path in paths if (finding := asset_finding(path, documented_folders)) is not None]


CHECK = PathCheck(
    check_id=CHECK_ID,
    title="Asset Placement",
    summary=(
        "Images, icons, fonts, audio, and video outside an assets/ folder, or loose at the root of assets/. "
        "Framework locations (public/, static/, Android res/, *.xcassets, Next.js app icons), documentation, "
        "test fixtures, and dot folders such as .github/ are exempt."
    ),
    run=check_asset_location,
)
