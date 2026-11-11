import re
from pathlib import Path, PurePath

from pristine.checks.definitions import PathCheck
from pristine.files.path_roles import is_test_path, is_vendored
from pristine.reports.findings import Finding, Severity
from pristine.services.git import edited_since_default_branch, repository_root

RULE_ID = "CO-14"
MIGRATIONS_FOLDER = "migrations"
ALEMBIC_FOLDERS = (("alembic", "versions"), ("migrations", "versions"))
RAILS_FOLDERS = ("db", "migrate")
PYTHON_PACKAGE_MARKER = "__init__.py"
NUMBERED_PYTHON_MIGRATION = re.compile(r"\d+_\w+\.py")
NUMBERED_SQL_MIGRATION = re.compile(r"\d+[_.-].*\.sql")
PRISMA_MIGRATION_FOLDER = re.compile(r"\d+_.+")
PRISMA_MIGRATION_FILE = "migration.sql"
MESSAGE = (
    "migration already merged on the default branch was edited; environments that ran it keep the old schema. "
    "Restore it and ship the change as a new migration"
)


def is_alembic_revision(path: PurePath) -> bool:
    is_module = path.suffix == ".py" and path.name != PYTHON_PACKAGE_MARKER
    return is_module and path.parts[-3:-1] in ALEMBIC_FOLDERS


def is_prisma_migration(path: PurePath) -> bool:
    in_migration_folder = PRISMA_MIGRATION_FOLDER.fullmatch(path.parent.name) is not None
    return path.name == PRISMA_MIGRATION_FILE and in_migration_folder and path.parent.parent.name == MIGRATIONS_FOLDER


def is_numbered_migration(path: PurePath) -> bool:
    numbered = NUMBERED_PYTHON_MIGRATION.fullmatch(path.name) or NUMBERED_SQL_MIGRATION.fullmatch(path.name)
    return path.parent.name == MIGRATIONS_FOLDER and numbered is not None


def is_migration(path: PurePath) -> bool:
    if is_test_path(path) or is_vendored(path):
        return False
    is_rails = path.suffix == ".rb" and path.parts[-3:-1] == RAILS_FOLDERS
    return is_rails or is_alembic_revision(path) or is_numbered_migration(path) or is_prisma_migration(path)


def edited_in_repository(location: Path, root: Path | None, edited: dict[Path, frozenset[str] | None]) -> bool:
    if root is None:
        return False
    names = edited.get(root)
    return names is not None and location.relative_to(root).as_posix() in names


def check_edited_migrations(paths: list[str]) -> list[Finding]:
    migrations = {path: Path(path).resolve() for path in paths if is_migration(PurePath(path))}
    roots = {folder: repository_root(folder) for folder in {location.parent for location in migrations.values()}}
    edited = {root: edited_since_default_branch(root) for root in set(roots.values()) if root is not None}
    return [
        Finding(path, 1, RULE_ID, Severity.ERROR, MESSAGE)
        for path, location in migrations.items()
        if edited_in_repository(location, roots[location.parent], edited)
    ]


CHECK = PathCheck(
    rule_id=RULE_ID,
    title="Changes to Merged Migrations",
    summary=(
        "Migration files (Alembic versions/, Django and SQL numbered migrations/, Rails db/migrate/, Prisma "
        "migration.sql) that exist on the origin default branch and whose content differs from it in the working "
        "tree or on the current branch; whitespace-only edits and unknown git state are not reported."
    ),
    run=check_edited_migrations,
)
