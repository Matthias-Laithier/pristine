# CR-23 Code Is Greppable

Every name a reader looks for appears literally in the source, and every import leads straight to the definition. Never build an attribute name, a function name, a module path, or a global name from a runtime value. Import each name from the module that defines it, under its own name. A package re-exports only through its single public entry point, such as `__init__.py` or `index.ts`, and nothing else re-exports.

Agents and people navigate code by text search and by following imports. A name built at runtime, such as `getattr(handlers, f"on_{event_type}")`, has no definition that a search can find and no caller that a search can list, so a rename silently breaks it and a deletion looks safe when it is not. A re-export chain or an alias makes the reader resolve several files before reaching the definition, and the same function shows up under several names. When declaration and use share one spelling and one path, a single search answers "where is this defined" and "who calls this".

The requirements:
- Dynamic lookup takes a literal name: `getattr`, `setattr`, `hasattr`, `delattr`, `importlib.import_module`, `__import__`, `globals()[...]`, a dynamic `import()`, and a computed member built from a template string. Dispatch over runtime values goes through a registry literal (see [CR-14](cr-14-value-dispatch-through-a-registry.md)).
- Imports bind the defined name. An alias is allowed only to resolve a collision between two imported names in the same file, or for a name the ecosystem always aliases, such as `numpy as np`.
- No wildcard imports. No barrel files inside a package: an `index.ts` or `__init__.py` re-exports only at the public boundary of a package that other packages consume (see [CO-11](co-11-export-only-the-public-contract.md)).
- One concept has one name across the code base, the storage, and the API. Never rename a field at each layer, such as `user_id` in the database, `userId` in the API, and `uid` in the domain, unless an external contract fixes the spelling.

The exceptions:
- Generic code whose input is the name itself, such as a serializer that walks the fields of a dataclass or a framework adapter that resolves a configured dotted path. Keep it in one module at the edge and give it a test.
- Generated code, which keeps what its generator writes (see [CR-3](cr-3-no-comments-except-machine-read-text.md)).

[CR-4](cr-4-naming.md) owns what a name says. This rule owns whether the name can be found.

## Bad

```python
import importlib

from billing.handlers import invoice_handlers as handlers


def run_billing_job(job):
    module = importlib.import_module(f"billing.jobs.{job.kind}")
    handler = getattr(handlers, f"on_{job.kind}")
    return handler(module.load(job))
```

A search for `on_refund` finds no caller, and `billing.jobs.refund` looks unused. Renaming either breaks the job at runtime with no static signal.

## Good

```python
from billing.handlers import on_invoice, on_refund
from billing.jobs import load_invoice, load_refund

JOB_STEPS = {
    "invoice": (load_invoice, on_invoice),
    "refund": (load_refund, on_refund),
}


def run_billing_job(job):
    load, handle = JOB_STEPS[job.kind]
    return handle(load(job))
```

A search for `on_refund` lands on its definition and on its single use. The supported job kinds are listed in one literal, and a renamed function fails at import.
