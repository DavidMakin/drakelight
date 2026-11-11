---
name: python
description: >-
  Conventions for writing Python in a repository: gates, toolchain, style, docstrings, and tests.
  Use when creating or editing Python code, or creating or changing a Python project.
  Not for work that does not touch Python.
---

# Python

Gates enforce, this skill guides.
Formatting, lint rules and types belong in automated checks, not in agent memory.
Set up the gates below when you create a Python project or are asked to add them.
When you edit a project without them, say so, but do not make the change depend on adding them.
Where the repository's `AGENTS.md` says otherwise, that rule wins.

## Gates

A Python project configures `ruff` (lint and format) and `mypy` in strict mode.
Start from the templates in this directory:

- [`templates/pyproject.toml`](templates/pyproject.toml) holds the `ruff` and `mypy` configuration and the dev dependency group.
- [`templates/pre-commit-config.yaml`](templates/pre-commit-config.yaml) holds the `ruff` hooks.

In a pull-request gate, run `ruff check .`, `mypy` and `pytest` for each project.
Treat pytest exit code 5 (no tests collected) as a pass, so a new project without tests does not fail.

## Toolchain

- Use `uv`, with a `pyproject.toml`, `uv.lock` and `.python-version` per project.
- In a repository with several uv projects:
  - Run commands in the owning project: set the working directory to the project, or use `uv run --project <dir> ...`.
  - Never run root `uv run ...` with `--python <version>` for a project.
    It keeps the root dependency groups and changes only the interpreter.
  - Do not add a Python service to a root uv workspace only to share dependencies.
    Declare a path dependency in its `[tool.uv.sources]`.
- Use Python 3.14 for new code.
- A project's own `pyproject.toml` and `.python-version` are authoritative.
  A lower pin is a dependency constraint, not drift.
- Never raise a pin without checking what the project's dependencies actually resolve on.

## Style

- Follow the [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html) with strict typing.
- Name files `snake_case.py`.
- Use Pydantic v2 for models. Configure them with `model_config = ConfigDict(...)`, never a v1 `class Config:` block.
  Add `plugins = ["pydantic.mypy"]` to `[tool.mypy]` in a project that uses it.
- Write documentation, comments and commit messages in British English.

## Docstrings

Use [Google style](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings).
A docstring describes what a function or class does, not the implementation steps it takes.
Type information belongs in type hints, not repeated in the docstring body or `Args` and `Returns` sections.
Document semantic constraints that the type hints do not show: units, valid ranges, ordering assumptions, side effects and preconditions.
Ticket IDs do not belong in docstrings.
Put ticket references in comments, commit messages, pull requests or the ticket itself.
Update the related docstrings when you change behaviour.
In review, a docstring that misstates a parameter, return value or raised error is a defect.
Docstrings do not need to be perfect, and occasional drift is acceptable.

Good:

```python
def merge_windows(first: Window, second: Window) -> Window:
    """Combine two time windows into one that covers both.

    The windows must share a timezone and overlap or touch; a gap between
    them means the result would claim time that neither window covers.

    Args:
        first: Earlier window; its start becomes the result's start.
        second: Later window; its end becomes the result's end.

    Returns:
        The smallest window containing both inputs.

    Raises:
        ValueError: If the timezones differ or the windows leave a gap.
    """
```

Bad, because it describes the implementation:

```python
def merge_windows(first: Window, second: Window) -> Window:
    """Compares the two start times, takes the smaller, then compares the ends and takes the larger."""
```

Bad, because it carries a ticket ID:

```python
def merge_windows(first: Window, second: Window) -> Window:
    """Combine two windows. XYZ-142: temporary workaround until batching lands."""
```

## Comments

- Remove comments that describe removed or changed behaviour.
- Trace a comment that claims a guarantee ("cannot hang", "always releases the lock") through the code before you trust it.
- Keep routine ticket and design justification out of names and comments.
  Keep a reference only when it explains a concrete constraint or workaround.
- State current truth.
  Leave out historical comparisons and changelog wording.

## Tests

- Tests prove the intended behaviour, not the current implementation, and would catch a regression in the concern the change addresses.
  Verify outputs and failure contracts, not private call order.
- New code paths in a file that has tests get new or updated test cases.
- A bug fix has a test that fails without the fix.
- Where skipping work is the point (a guard, a feature switch), a test verifies the work is skipped.
- Assertions check behaviour, not only that no error was thrown; no `if` guards around assertions.
- Error assertions name the expected error, not `raises(Exception)`.
- Edge cases (`None`, empty, boundary values) have their own assertions.
- No passthrough assertions: asserting `result.a == input.a` for a bare assignment proves nothing.
