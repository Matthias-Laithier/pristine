# CR-12 Function Size

30 lines is the target maximum for a function. 50 lines is the hard limit, and no function exceeds it. The rule covers functions and methods alike. Count every line of the definition as written, from the signature through the final statement, blank lines excluded. A definition past 30 lines needs a reason to stay whole. Past 50 lines there is no reason, only a split that has not happened yet.

Length is a symptom. A function that grows past 30 lines is accumulating jobs: parsing, validating, computing, writing, sending. Every job is another reason to change (see [CO-2](co-2-small-focused-units.md)), and one name cannot say what five jobs do.

The remedy is extraction along real jobs into named helpers, each owning one job. Cutting a function into `register_user_part_1` and `register_user_part_2` lowers the count and keeps the debt, since the pieces mean nothing alone. Extracted validation has a second payoff: it converts untrusted input into a trusted value once (see [BS-1](bs-1-validate-untrusted-input-at-the-boundary.md)).

This rule pairs with [CR-1](cr-1-code-file-size.md) and replaces nothing in it. CR-1 owns files, this rule owns functions. A file within its limit can still hold one 40-line function, and a compliant function does not keep its file small. Both rules must hold. [CR-17](cr-17-keep-function-signatures-cohesive.md) owns the inputs, and [CR-19](cr-19-keep-one-level-of-abstraction-per-function.md) owns vertical consistency inside the body.

The exceptions:
- An exhaustive `match` over many variants where every branch is one clause. Splitting it scatters a table that reads better whole.
- Generated files, which keep the shape their generator writes (see [CR-3](cr-3-no-comments-except-machine-read-text.md)).

## Bad

```python
from collections.abc import Mapping


def register_user(user_store, payload):
    if not isinstance(payload, Mapping):
        raise ValueError("payload must be a mapping")
    email_address = payload.get("email_address")
    display_name = payload.get("display_name")
    password_text = payload.get("password")
    accepts_marketing = payload.get("accepts_marketing")
    preferred_language = payload.get("preferred_language")
    if not isinstance(email_address, str) or "@" not in email_address:
        raise ValueError("email_address must be a valid email")
    if not isinstance(display_name, str) or not display_name.strip():
        raise ValueError("display_name must be a non-empty string")
    if not isinstance(password_text, str) or len(password_text) < 12:
        raise ValueError("password must be at least 12 characters")
    if not isinstance(accepts_marketing, bool):
        raise ValueError("accepts_marketing must be a boolean")
    if preferred_language not in SUPPORTED_LANGUAGES:
        raise ValueError("preferred_language is not supported")
    user = User(
        email_address=email_address,
        display_name=display_name,
        password_hash=hash_password(password_text),
        preferred_language=preferred_language,
        accepts_marketing=accepts_marketing,
    )
    try:
        user_store.create_user_trial_and_welcome_intent_if_email_available(
            user,
            format_welcome_message(display_name),
            timeout=3,
        )
    except EmailAlreadyRegistered as error:
        raise RegistrationConflict(email_address) from error
    return user
```

The definition runs 34 lines and holds four jobs: validate the payload, build the user, format the welcome message, and persist the registration with its email intent. Any change to signup lands in this one body, and a reader must scan all 34 lines to find the line they came for.

## Good

```python
from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class RegistrationRequest:
    email_address: str
    display_name: str
    password_text: str
    accepts_marketing: bool
    preferred_language: str


def parse_registration_request(payload):
    if not isinstance(payload, Mapping):
        raise ValueError("payload must be a mapping")
    email_address = payload.get("email_address")
    display_name = payload.get("display_name")
    password_text = payload.get("password")
    accepts_marketing = payload.get("accepts_marketing")
    preferred_language = payload.get("preferred_language")
    if not isinstance(email_address, str) or "@" not in email_address:
        raise ValueError("email_address must be a valid email")
    if not isinstance(display_name, str) or not display_name.strip():
        raise ValueError("display_name must be a non-empty string")
    if not isinstance(password_text, str) or len(password_text) < 12:
        raise ValueError("password must be at least 12 characters")
    if not isinstance(accepts_marketing, bool):
        raise ValueError("accepts_marketing must be a boolean")
    if preferred_language not in SUPPORTED_LANGUAGES:
        raise ValueError("preferred_language is not supported")
    return RegistrationRequest(
        email_address=email_address,
        display_name=display_name,
        password_text=password_text,
        accepts_marketing=accepts_marketing,
        preferred_language=preferred_language,
    )


def register_user(user_store, payload):
    request = parse_registration_request(payload)
    user = User(
        email_address=request.email_address,
        display_name=request.display_name,
        password_hash=hash_password(request.password_text),
        preferred_language=request.preferred_language,
        accepts_marketing=request.accepts_marketing,
    )
    try:
        user_store.create_user_trial_and_welcome_intent_if_email_available(
            user,
            format_welcome_message(user.display_name),
            timeout=3,
        )
    except EmailAlreadyRegistered as error:
        raise RegistrationConflict(request.email_address) from error
    return user
```

The definition is an orchestration of named jobs: parse, build, format, and persist. Validation lives in one helper that hands back a trusted value, and each job can change without touching the others. The store creates the user, the trial, and the durable welcome-email intent atomically, and rejects a duplicate email without a check-then-write race.
