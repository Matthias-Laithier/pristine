from collections.abc import Callable
from pathlib import Path

import pytest

from pristine.cli import main
from tests.conftest import JsonReport, RunPristine, parsed_report, run_git

type SeedRepository = Callable[[dict[str, str]], Path]

COMMIT_OPTIONS = ("-c", "user.name=Ada", "-c", "user.email=ada@example.com", "-c", "commit.gpgsign=false")
ADD_EMAIL = "def upgrade(op):\n    op.add_column('customers', 'email')\n"
RENAME_EMAIL = "def upgrade(op):\n    op.rename_column('customers', 'email', 'contact_email')\n"
ADD_PHONE = "def upgrade(op):\n    op.add_column('customers', 'phone')\n"
CREATE_ORDERS = "CREATE TABLE orders (id integer);\n"
CREATE_ORDERS_WITH_TOTAL = "CREATE TABLE orders (id integer, total integer);\n"
SEND_INVOICE = "def send_invoice(invoice):\n    return invoice\n"


def commit_all(directory: Path, message: str) -> None:
    run_git(directory, "add", "--all")
    run_git(directory, *COMMIT_OPTIONS, "commit", "--quiet", "--no-verify", "-m", message)


def write_files(directory: Path, files: dict[str, str]) -> None:
    for name, content in files.items():
        (directory / name).parent.mkdir(parents=True, exist_ok=True)
        (directory / name).write_text(content)


@pytest.fixture
def seed_repository(tmp_path: Path, tmp_path_factory: pytest.TempPathFactory) -> SeedRepository:
    origin = tmp_path_factory.mktemp("origin") / "origin.git"

    def seed(files: dict[str, str]) -> Path:
        run_git(origin.parent, "init", "--quiet", "--bare", "--initial-branch=main", origin.name)
        run_git(tmp_path, "init", "--quiet", "--initial-branch=main")
        write_files(tmp_path, files)
        commit_all(tmp_path, "seed")
        run_git(tmp_path, "remote", "add", "origin", str(origin))
        run_git(tmp_path, "push", "--quiet", "origin", "main")
        run_git(tmp_path, "remote", "set-head", "origin", "main")
        run_git(tmp_path, "checkout", "--quiet", "-b", "feature")
        return origin

    return seed


def edited_migrations(report: JsonReport) -> list[tuple[str, str]]:
    return [(finding["path"], finding["severity"]) for finding in report["findings"] if finding["rule_id"] == "CO-14"]


def test_only_the_edited_migration_is_reported(
    run_pristine: RunPristine, seed_repository: SeedRepository, tmp_path: Path
) -> None:
    seed_repository({"alembic/versions/a1_add_email.py": ADD_EMAIL, "billing.py": SEND_INVOICE})
    write_files(tmp_path, {"alembic/versions/b2_add_phone.py": ADD_PHONE})
    commit_all(tmp_path, "add phone")
    files = {"alembic/versions/c3_add_city.py": ADD_PHONE, "billing.py": SEND_INVOICE + "\n\nRATE = 2\n"}
    _, report = run_pristine({**files, "alembic/versions/a1_add_email.py": RENAME_EMAIL})
    assert edited_migrations(report) == [("alembic/versions/a1_add_email.py", "error")]


def test_edit_committed_on_the_current_branch_is_reported(
    run_pristine: RunPristine, seed_repository: SeedRepository, tmp_path: Path
) -> None:
    seed_repository({"db/migrate/20240101000000_create_orders.rb": "class CreateOrders\nend\n"})
    write_files(tmp_path, {"db/migrate/20240101000000_create_orders.rb": "class CreateOrders\n  TOTAL = 1\nend\n"})
    commit_all(tmp_path, "edit migration")
    _, report = run_pristine({})
    assert edited_migrations(report) == [("db/migrate/20240101000000_create_orders.rb", "error")]


@pytest.mark.parametrize(
    ("name", "contents", "reported"),
    [
        ("shop/migrations/0001_initial.py", (ADD_EMAIL, RENAME_EMAIL), True),
        ("migrations/versions/9f2c_add_email.py", (ADD_EMAIL, RENAME_EMAIL), True),
        ("migrations/000001_create_orders.up.sql", (CREATE_ORDERS, CREATE_ORDERS_WITH_TOTAL), True),
        ("prisma/migrations/20240101000000_init/migration.sql", (CREATE_ORDERS, CREATE_ORDERS_WITH_TOTAL), True),
        ("shop/migrations/__init__.py", ("", "VERSION = 1\n"), False),
        ("tests/migrations/0001_initial.py", (ADD_EMAIL, RENAME_EMAIL), False),
        ("migrations/schema.sql", (CREATE_ORDERS, CREATE_ORDERS_WITH_TOTAL), False),
        ("shop/migrations/0001_initial.py", (ADD_EMAIL, ADD_EMAIL.replace("    ", "        ") + "\n"), False),
    ],
)
def test_migration_layouts(
    run_pristine: RunPristine, seed_repository: SeedRepository, name: str, contents: tuple[str, str], reported: bool
) -> None:
    original, edited = contents
    seed_repository({name: original})
    _, report = run_pristine({name: edited})
    assert edited_migrations(report) == ([(name, "error")] if reported else [])


def test_repository_without_remote_reports_nothing(run_pristine: RunPristine, tmp_path: Path) -> None:
    run_git(tmp_path, "init", "--quiet", "--initial-branch=main")
    write_files(tmp_path, {"alembic/versions/a1_add_email.py": ADD_EMAIL})
    commit_all(tmp_path, "seed")
    _, report = run_pristine({"alembic/versions/a1_add_email.py": RENAME_EMAIL})
    assert edited_migrations(report) == []


def test_directory_outside_git_reports_nothing(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"alembic/versions/a1_add_email.py": RENAME_EMAIL})
    assert edited_migrations(report) == []


def test_shallow_clone_reports_nothing(
    seed_repository: SeedRepository,
    tmp_path: Path,
    tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    origin = seed_repository({"alembic/versions/a1_add_email.py": ADD_EMAIL})
    clone = tmp_path_factory.mktemp("clone") / "shop"
    run_git(tmp_path, "clone", "--quiet", "--depth", "1", f"file://{origin}", str(clone))
    write_files(clone, {"alembic/versions/a1_add_email.py": RENAME_EMAIL})
    monkeypatch.chdir(clone)
    main(["check", ".", "--json"])
    assert edited_migrations(parsed_report(capsys.readouterr().out)) == []
