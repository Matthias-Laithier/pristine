# CR-6 Global Variables Are Defined at the Top of the File

Every global variable is defined at the top of its file, right after the imports. A reader opening the file finds all file-level state in one place. Nobody hunts for definitions buried between functions or discovers one only after stepping through the code. A global declared mid-file is invisible state: it hides from review, and readers assume the wrong thing about what exists.

The exception is a file-level value that must read an earlier definition in the same file. Put it directly below what it derives from, still in the top block of the file, and never below an unrelated definition.

This rule defines where globals live. It does not cover when runtime configuration is acquired. [CO-13](co-13-imports-do-not-perform-external-work.md) forbids reading the environment, the filesystem, or another external source during import. Acquire runtime configuration in the composition root and pass it to the code that needs it.

## Bad

```python
DEFAULT_SMTP_PORT = 587


def create_email_settings(smtp_host, email_log_path):
    return EmailSettings(
        smtp_host=smtp_host,
        smtp_port=DEFAULT_SMTP_PORT,
        log_path=email_log_path,
    )


DEFAULT_EMAIL_RETRY_COUNT = 3
```

`DEFAULT_EMAIL_RETRY_COUNT` is invisible to a reader of `create_email_settings`, who assumes the file-level configuration is `DEFAULT_SMTP_PORT` alone. A new reader must scan the entire file to assemble the full picture.

## Good

```python
DEFAULT_SMTP_PORT = 587
DEFAULT_EMAIL_RETRY_COUNT = 3


def create_email_settings(smtp_host, email_log_path):
    return EmailSettings(
        smtp_host=smtp_host,
        smtp_port=DEFAULT_SMTP_PORT,
        log_path=email_log_path,
    )
```

Same startup assembly, and opening the file shows the complete file-level state in the first ten lines. Review of a new global happens where all the others live.

Globals gathered at the top are config, and config is never mutated. See [CR-7](cr-7-global-variables-are-config-never-mutated.md).
