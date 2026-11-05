# BS-15 Log Diagnosable Events, Never Personal Data

Operational output goes through the logging library of the ecosystem, at the level that matches its audience: error for a failure that needs action, warning for a handled degradation, info for lifecycle events, debug for detail. Each record is a constant message plus structured fields, and carries the correlation identifier of its request, job, or workflow run. A failure is logged once, with its traceback, at the boundary that handles it. Records carry identifiers and sizes. They never carry personal data, request payloads, prompts, or model outputs.

Logs are the only witness when production breaks. A message built by interpolation cannot be grouped or counted, `print` bypasses levels and handlers, logging at every layer multiplies one failure into five records, and a message without the traceback hides where the failure happened. A copied payload moves personal data into a store with weaker access control and longer retention.

The exceptions:
- A command-line program writes its user-facing output to standard output and standard error. That output is its interface.
- An audit trail that must hold personal data lives in a dedicated store with its own access control and retention.

[BS-2](bs-2-keep-secrets-out-of-code-and-output.md) owns secrets in every output. [BS-4](bs-4-do-not-swallow-failures.md) owns whether a failure may be handled. [BS-9](bs-9-boundaries-expose-stable-error-contracts.md) owns what the caller receives.

## Bad

```python
import logging

logger = logging.getLogger(__name__)


def handle_import_request(customer_importer, request):
    try:
        customer_importer.import_customer(request.payload, timeout=3)
    except InvalidCustomer as error:
        logger.error(f"import failed for {request.payload}: {error}")
        return ImportResponse.rejected(error.reason)
    return ImportResponse.accepted()
```

Names and email addresses land in the log store. Every record has a unique message that no dashboard can group, a handled rejection pages on-call at error level, and nothing links the record to its request.

## Good

```python
import logging

logger = logging.getLogger(__name__)


def handle_import_request(customer_importer, request):
    try:
        customer_importer.import_customer(request.payload, timeout=3)
    except InvalidCustomer as error:
        logger.warning(
            "customer import rejected",
            extra={"request_identifier": request.identifier, "reason": error.reason},
        )
        return ImportResponse.rejected(error.reason)
    return ImportResponse.accepted()
```

One constant message groups every rejection, the fields say which request and why, and no personal data leaves the application.
