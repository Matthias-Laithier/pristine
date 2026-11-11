import json
from pathlib import Path

import pytest

from pristine.cli.main import main
from tests.conftest import JsonReport, RunPristine, run_git

DEEP_CHAIN_LENGTH = 1100


def reported_cycles(report: JsonReport) -> list[tuple[str, int, str]]:
    return [
        (finding["path"], finding["line"], finding["message"].removeprefix("import cycle ").split(";")[0])
        for finding in report["findings"]
        if finding["check_id"] == "DEP-3" and finding["severity"] == "error"
    ]


def test_lazy_and_type_checking_imports_close_a_cycle(run_pristine: RunPristine) -> None:
    exit_code, report = run_pristine(
        {
            "src/shop/__init__.py": "",
            "src/shop/orders.py": (
                "from typing import TYPE_CHECKING\n\nif TYPE_CHECKING:\n    from shop.discounts import discount_for\n"
            ),
            "src/shop/discounts.py": "import json\n\n\ndef discount_for(order):\n    from shop import orders\n",
        }
    )
    assert exit_code == 1
    assert reported_cycles(report) == [
        ("src/shop/discounts.py", 5, "src/shop/discounts.py -> src/shop/orders.py -> src/shop/discounts.py")
    ]


def test_native_lazy_imports_close_a_cycle(run_pristine: RunPristine) -> None:
    exit_code, report = run_pristine(
        {"orders.py": "lazy from invoices import total\n", "invoices.py": "import orders\n"}
    )
    assert exit_code == 1
    assert reported_cycles(report) == [("invoices.py", 1, "invoices.py -> orders.py -> invoices.py")]


@pytest.mark.parametrize(
    ("files", "expected"),
    [
        ({"shop/__init__.py": "from .orders import Order\n", "shop/orders.py": "from shop import tax\n"}, []),
        (
            {"shop/__init__.py": "from .orders import Order\n", "shop/orders.py": "from shop import TAX_RATE\n"},
            [("shop/__init__.py", 1, "shop/__init__.py -> shop/orders.py -> shop/__init__.py")],
        ),
        (
            {"shop/billing/__init__.py": "", "shop/billing/invoice.py": "from ..orders import Order\n"},
            [("shop/billing/invoice.py", 1, "shop/billing/invoice.py -> shop/orders.py -> shop/billing/invoice.py")],
        ),
    ],
)
def test_from_imports_resolve_to_the_submodule_or_else_the_package(
    run_pristine: RunPristine, files: dict[str, str], expected: list[tuple[str, int, str]]
) -> None:
    shop = {"shop/__init__.py": "", "shop/tax.py": "", "shop/orders.py": "from .billing.invoice import draft\n"}
    _, report = run_pristine(shop | files)
    assert reported_cycles(report) == expected


def test_namespace_packages_resolve_without_shadowing_third_party_names(run_pristine: RunPristine) -> None:
    _, report = run_pristine(
        {
            "src/acme/billing/__init__.py": "",
            "src/acme/billing/invoices.py": "import fastapi\nfrom acme.ledger.entries import Entry\n",
            "src/acme/ledger/__init__.py": "",
            "src/acme/ledger/entries.py": "from acme.billing.invoices import Invoice\n",
            "src/acme/fastapi/__init__.py": "from acme.billing.invoices import Invoice\n",
        }
    )
    assert reported_cycles(report) == [
        (
            "src/acme/billing/invoices.py",
            2,
            "src/acme/billing/invoices.py -> src/acme/ledger/entries.py -> src/acme/billing/invoices.py",
        )
    ]


def test_unresolvable_and_unparsable_imports_are_ignored(run_pristine: RunPristine) -> None:
    _, report = run_pristine(
        {
            "orders.py": "import importlib\nimport requests\n\nimportlib.import_module(MODULE_NAME)\nimport discounts\n",
            "discounts.py": "def broken(:\n    import orders\n",
            "receipts.py": "importlib.import_module(f'{orders}')\n",
        }
    )
    assert reported_cycles(report) == []


def test_relative_script_imports_of_every_form_close_a_cycle(run_pristine: RunPristine) -> None:
    _, report = run_pristine(
        {
            "web/cart.ts": "// import './checkout'\nconst hint = \"import './checkout'\";\nimport type { Price } from './price';\n",
            "web/price.ts": "export * from './money';\n",
            "web/money/index.ts": "const checkout = require('../checkout.js');\n",
            "web/checkout.ts": "export async function open() {\n  return import('./cart');\n}\n",
        }
    )
    assert reported_cycles(report) == [
        ("web/cart.ts", 3, "web/cart.ts -> web/price.ts -> web/money/index.ts -> web/checkout.ts -> web/cart.ts")
    ]


def test_a_component_with_several_cycles_is_reported_once(run_pristine: RunPristine) -> None:
    _, report = run_pristine(
        {"cart.py": "import price\n", "price.py": "import cart\nimport tax\n", "tax.py": "import price\n"}
    )
    assert reported_cycles(report) == [
        ("cart.py", 1, "cart.py -> price.py -> cart.py, one of the cycles among 3 mutually dependent files")
    ]


def test_a_cycle_deeper_than_the_recursion_limit_is_found(run_pristine: RunPristine) -> None:
    files = {
        f"step_{index:04}.py": f"import step_{(index + 1) % DEEP_CHAIN_LENGTH:04}\n"
        for index in range(DEEP_CHAIN_LENGTH)
    }
    _, report = run_pristine(files)
    assert [(path, line) for path, line, _ in reported_cycles(report)] == [("step_0000.py", 1)]


def test_a_cycle_through_an_unchecked_repository_file_is_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    run_git(tmp_path, "init", "--quiet")
    files = {"orders.py": "import invoices\n", "invoices.py": "import discounts\n", "discounts.py": "import orders\n"}
    files |= {"tax.py": "import rates\n", "rates.py": "import tax\n"}
    for name, content in files.items():
        Path(name).write_text(content)
    main(["check", "orders.py", "--json"])
    assert reported_cycles(json.loads(capsys.readouterr().out)) == [
        ("orders.py", 1, "orders.py -> invoices.py -> discounts.py -> orders.py")
    ]
