# CR-3 No Comments Except Machine-Read Text

No comments in code. Docstrings are comments. The code must be clear enough to document itself. If a comment feels necessary, the code is unclear. Refactor until it reads like prose.

The exceptions are text that a program reads. The test: delete the text and check whether any program's behavior or output changes. If it changes, the text is an instruction or data written in comment syntax. If nothing changes, it is a comment, and it goes.

- Toolchain directives: shebangs, pragmas, compiler directives, linter directives, and similar instructions required for the code to execute or pass tooling. They are instructions to the toolchain and count as no comment.
- Generated files: files produced by a generation tool, static or dynamic, keep the comments the tool writes. Never strip them by hand, since they come back on the next generation run. If the file needs a comment the tool does not write, change the generator or its template and leave the generated file untouched.
- Interface descriptions read by a framework: some frameworks turn a docstring into the description their consumer receives. Examples are MCP tools, resources, and prompts, LLM function-calling tools such as those of the OpenAI Agents SDK, Pydantic AI, or LangChain, CLI commands built with Click or Typer, and HTTP endpoints whose framework publishes the docstring to OpenAPI, such as FastAPI. The consumer, an agent, a terminal user, or an API client, sees the description and never the code. A name alone cannot say when to call the unit, what an argument means, or what side effect it performs. On these units the description is required.
- Published API reference: a library that builds and publishes a generated reference with a tool such as Sphinx, rustdoc, or godoc documents its public surface (see [CO-11](co-11-export-only-the-public-contract.md)) with the doc comments the generator reads. A project that publishes no reference has no such exception.

When you take one of the last two exceptions:
- Describe only the units the framework or generator exposes. The helpers behind them stay free of comments.
- Write for the consumer: what the unit does, when to use it, what each argument means, what it returns, its side effects and its failures. Never describe the implementation.
- Put each fact where the framework reads it. Use structured fields when the framework offers them, such as parameter descriptions in the schema or a read-only hint. Text the framework does not parse, such as an `Args:` section it ignores, is a comment.
- Keep the description true. It is part of the interface contract (see [CO-4](co-4-clear-interfaces.md)), and a behavior change updates it in the same change (see [CR-11](cr-11-every-change-includes-cleanup.md)).

Doctests pass the deletion test and stay excluded: they put tests inside the source, which [TST-4](tst-4-tests-live-in-a-dedicated-tests-folder.md) forbids.

Naming comes first. A description supplements a clear name for a consumer who cannot read the code. It never excuses an unclear name (see [CR-4](cr-4-naming.md)).

## Bad

```python
from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field

mcp = FastMCP("Invoices")


@mcp.tool
def find_overdue_invoices(
    customer_identifier: str,
    minimum_days_overdue: Annotated[int, Field(ge=0)],
):
    return [
        summarize_invoice(invoice)
        for invoice in list_overdue_invoices(
            customer_identifier,
            minimum_days_overdue,
        )
    ]


def summarize_invoice(invoice):
    """Summarize an invoice."""
    # due date as an ISO string so it serializes to JSON
    return {
        "invoice_number": invoice.number,
        "amount_in_cents": invoice.amount_in_cents,
        "due_date": invoice.due_date.isoformat(),
    }
```

The agent receives a tool name, two parameter names, and nothing else. It must guess whether the identifier is an email or an account ID, from which date the days count, and whether calling the tool sends reminders. Meanwhile the helper carries text no program reads: a docstring that repeats its name and a comment that narrates `isoformat`.

## Good

```python
from typing import Annotated

from fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

mcp = FastMCP("Invoices")


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
def find_overdue_invoices(
    customer_identifier: Annotated[
        str,
        Field(description="Billing account ID, such as ACC-1042. Not an email address."),
    ],
    minimum_days_overdue: Annotated[
        int,
        Field(description="Minimum days elapsed since the due date.", ge=0),
    ],
):
    """List a customer's unpaid invoices past their due date.

    Use it to check what a customer owes before drafting a payment reminder.
    """
    return [
        summarize_invoice(invoice)
        for invoice in list_overdue_invoices(
            customer_identifier,
            minimum_days_overdue,
        )
    ]


def summarize_invoice(invoice):
    return {
        "invoice_number": invoice.number,
        "amount_in_cents": invoice.amount_in_cents,
        "due_date": invoice.due_date.isoformat(),
    }
```

Every fact the agent needs reaches it through a field FastMCP reads. The docstring becomes the tool description, the `Field` descriptions land in the parameter schema, and the read-only hint is structured metadata. The helper is invisible to the agent and carries no text, so nothing drifts out of date behind the interface.
