# CO-6 Wrap External Clients in Singleton Services

An external client is anything with real construction cost or operational state: an HTTP client, a database pool, a message broker client, a cloud SDK. Wrap it in a service class and reuse one instance for each distinct configuration and execution context. Create it at application startup. The service exposes the operations the application actually needs, and business logic never constructs the underlying client.

Recreating a client on every call repeats setup and throws away reuse such as connection pooling. Wrapping it in a service also makes the application depend on a narrow interface, and the full SDK surface of the client stays hidden. See [CO-4](co-4-clear-interfaces.md).

A singleton describes the lifecycle of the service. It says nothing about how consumers reach it. Create the instance in the application's composition root and pass it to consumers. A stable global service is also acceptable when its identity and configuration never change and it holds no mutable application state. Internal client state such as connection pools, token caches, and retries is operational state and stays encapsulated. See [CR-7](cr-7-global-variables-are-config-never-mutated.md).

Never share a client beyond the lifecycle or concurrency model it supports. Per-tenant credentials, per-request user tokens, separate event loops, clients that are not thread-safe, and test fakes require separate instances. Each service lives in its own file inside the component's `services/` folder (see [CR-8](cr-8-services-live-in-a-dedicated-services-folder.md)). The composition root also owns cleanup at the end of the application's life (see [BS-8](bs-8-resources-have-explicit-owners-and-lifetimes.md)).

## Bad

```python
class InvoiceStoreUnavailable(Exception):
    pass


def download_invoice(client_factory, bucket, invoice_identifier):
    with client_factory.create(
        connect_timeout=3,
        read_timeout=3,
    ) as client:
        try:
            return client.download(
                bucket,
                invoice_identifier,
            )
        except ObjectStoreUnavailable as error:
            raise InvoiceStoreUnavailable from error


def upload_invoice(client_factory, bucket, invoice_identifier, content):
    with client_factory.create(
        connect_timeout=3,
        read_timeout=3,
    ) as client:
        try:
            client.upload(
                bucket,
                invoice_identifier,
                content,
            )
        except ObjectStoreUnavailable as error:
            raise InvoiceStoreUnavailable from error
```

Every operation builds a new client. Setup repeats, connection reuse is lost, and the client lifecycle has no owner at the application level.

## Good

`services/invoice_store.py`:

```python
class InvoiceStoreUnavailable(Exception):
    pass


class InvoiceStore:
    def __init__(self, client, bucket):
        self.client = client
        self.bucket = bucket

    def download(self, invoice_identifier):
        try:
            return self.client.download(
                self.bucket,
                invoice_identifier,
            )
        except ObjectStoreUnavailable as error:
            raise InvoiceStoreUnavailable from error

    def upload(self, invoice_identifier, content):
        try:
            self.client.upload(
                self.bucket,
                invoice_identifier,
                content,
            )
        except ObjectStoreUnavailable as error:
            raise InvoiceStoreUnavailable from error
```

`main.py`:

```python
def main(settings):
    with create_object_store_client(
        connect_timeout=settings.connect_timeout,
        read_timeout=settings.read_timeout,
    ) as client:
        invoice_store = InvoiceStore(
            client,
            settings.invoice_bucket,
        )
        run_application(invoice_store)
```

The client and the service are built once at application startup and reused by every consumer. The composition root owns the lifetime of the client, the service exposes stable application errors, and tests can instantiate it with a fake client.
