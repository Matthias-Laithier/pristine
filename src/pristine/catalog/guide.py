GUIDE = """# Pristine guide

- Follow the user and the project's conventions.
- Start with the operation the caller needs. Name it, find its owner, search, then reuse or implement it there.
- Keep responsibilities cohesive. Use the smallest clear solution for the present requirement. Remove what the change makes obsolete.
- Keep domain decisions independent of concrete infrastructure. Assemble services at startup and pass dependencies explicitly.
- Validate untrusted input and authorize resource access. Preserve data invariants, atomicity, race safety, retry safety and deployed compatibility.
- Test observable behavior, boundaries and failure paths against independent expectations. Use deterministic tests for code and evals for model quality.
- Run relevant checks while working and the project gate before finishing. Report failures, meaningful exceptions and unverified behavior.
"""
