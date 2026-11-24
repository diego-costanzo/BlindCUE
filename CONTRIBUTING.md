# Contributing to BlindCUE

Thank you for your interest in contributing to **BlindCUE**!
BlindCUE is a failsafe audio/video cue player built for live shows. Because regressions or hidden side effects can disrupt a live performance, every contribution follows strict quality and governance rules.

Please read [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) before modifying application code.

---

## Core Contribution Rules

1. **One open Pull Request per contributor at a time**
   - You may have **at most 1 open PR** in this repository at any given time (unless explicitly waived by the maintainer).
   - Wait until your current PR is merged or closed before opening another one.

2. **Approved Issue required before new features**
   - Do **not** open a PR for a new feature without an **Issue reviewed and approved by the maintainer** first.
   - Open an Issue describing the use case, expected behavior, and scope, and wait for maintainer approval before writing feature code.
   - Small, clear bug fixes may reference an existing bug Issue (or include a minimal reproduction in the linked Issue).

3. **Small, single-purpose PRs**
   - Each PR must address **one single, well-defined purpose** (one bug fix or one focused approved feature).
   - Multi-feature bundle PRs will be closed without review.
   - Automated CI enforces a hard limit of **500 changed lines** (`additions + deletions`) and **15 changed files** per PR, unless the maintainer explicitly adds the `approved-large` label.

4. **Tests are mandatory**
   - Every behavioral change or bug fix must include appropriate automated tests under `tests/`.
   - The full headless test suite must pass:
     ```bash
     QT_QPA_PLATFORM=offscreen pytest -q tests/
     ```
   - Scene/state machine changes should also include unit tests in `tests/test_show_engine_pure.py`.

5. **Documentation and manuals must be updated in the same PR**
   - If your change alters user-facing behavior, shortcuts, UI, CLI, or configuration, you **must** update the relevant documentation in the **same PR**:
     - `README.md` (if high-level features/shortcuts/setup change)
     - `docs/MANUAL.md`
     - `docs/manual/manual_<lang>.src.html` and compiled `blindcue/help/manual_<lang>.html` (via `python tools/build_manual.py`)
     - `docs/ARCHITECTURE.md` (if module boundaries or architecture change)

6. **Code quality, security, and platform standards**
   - **Python 3.10+**, clean modern type hints, cross-platform compatibility (**Linux Wayland, Windows 10/11, macOS**).
   - **Open-source only**: no proprietary dependencies, no paid APIs, no cloud services, no telemetry/analytics, and no unexpected network calls or arbitrary filesystem access.
   - Run `ruff` and `bandit` locally on all Python files you add or modify before pushing:
     ```bash
     ruff check <your-changed-files>
     bandit -ll <your-changed-files>
     ```

---

## Pull Request Checklist

When opening a PR, you must fill out the entire `.github/PULL_REQUEST_TEMPLATE.md` truthfully:
- Link the approved Issue (`Closes #<id>` or `Fixes #<id>`).
- Explain concisely what changes and why.
- Complete all required checklist boxes (tests, lint/security, documentation, single-purpose scope).
- Disclose any AI assistance used and confirm that you personally reviewed, understood, and tested every line.

Automated CI checks (`pr-gatekeeper`) will fail if the PR template is incomplete, if the PR exceeds size limits without `approved-large`, if you have more than 1 open PR, or if `ruff`, `bandit`, or `pytest` fail.
