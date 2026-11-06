import pytest

from tests.conftest import RunPristine, rule_findings

IMAGE_BYTES = "PNG"


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("frontend/src/components/acme_logo.png", [(1, "error")]),
        ("frontend/Inter-Regular.ttf", [(1, "error")]),
        ("frontend/assets/images/acme_logo.png", []),
        ("frontend/assets/acme_logo.png", [(1, "warning")]),
        ("frontend/public/favicon.ico", []),
        ("frontend/static/acme_logo.svg", []),
        ("android/app/src/main/res/mipmap-hdpi/ic_launcher.png", []),
        ("ios/Billing/Assets.xcassets/AppIcon.appiconset/icon.png", []),
        ("frontend/src/app/favicon.ico", []),
        ("frontend/src/app/acme_logo.png", [(1, "error")]),
        ("docs/images/architecture.png", []),
        ("backend/tests/fixtures/scanned_invoice.png", []),
        ("frontend/src/components/InvoiceList.jsx", []),
    ],
)
def test_asset_location(run_pristine: RunPristine, path: str, expected: list[tuple[int, str]]) -> None:
    _, report = run_pristine({path: IMAGE_BYTES})
    assert rule_findings(report, "CR-9") == expected


def test_image_beside_markdown_is_documentation(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"billing/README.md": "# Billing\n", "billing/invoice_flow.png": IMAGE_BYTES})
    assert rule_findings(report, "CR-9") == []
