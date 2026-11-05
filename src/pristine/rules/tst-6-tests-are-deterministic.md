# TST-6 Tests Are Deterministic

Same code, same result, every run, every machine. Nondeterminism enters a test through the world outside the code: the wall clock, randomness, the network, external services, and the ordering of unordered things. The test never hopes for a stable environment. It controls its inputs. The date is injected, the randomness is seeded or faked, and external services are replaced with in-memory fakes. This is why collaborators are injected in the first place (see [CO-4](co-4-clear-interfaces.md)). Test doubles belong at the edges of the system or at stable owned boundaries where the interaction is contractual (see [TST-1](tst-1-test-behavior-through-the-public-interface.md)).

A flaky test is worse than no test when the nondeterminism comes from the test. Red that sometimes means nothing trains everyone to ignore red, and red is the only signal of the suite. Fix the determinism of that test, or quarantine it with an owner and a deadline until it is fixed. If a controlled test exposes nondeterministic application behavior, the test is valid: keep it and fix the application. A flaky test left in the required gate spends the credibility of the suite to keep one assertion.

## Bad

```python
def test_welcome_email_is_sent():
    register_user(email="marc@example.com")
    time.sleep(2)
    assert smtp_server.last_sent_message is not None
```

This test depends on a live SMTP server, the network between the process and that server, and a two-second guess about latency. It passes on a quiet machine and fails every third CI run. Once burned, the team re-runs red builds without reading them, and red starts meaning nothing.

## Good

```python
def test_welcome_email_is_sent():
    smtp = InMemorySMTP()
    register_user(email="marc@example.com", smtp=smtp)
    assert smtp.last_recipient == "marc@example.com"
    assert smtp.last_subject == "Welcome"
```

Same result on every machine, every run, in milliseconds. When this test is red, something in the code is broken, and that is the only thing red is ever allowed to mean.
