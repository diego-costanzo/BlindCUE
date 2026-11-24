## Linked Issue

Closes #<!-- Replace with the approved Issue number, e.g. Closes #123 -->

## What Changes (Single Purpose)

<!-- Describe concisely what this PR changes and why. Keep it strictly focused on one single goal. -->

- **User-facing behavior changed:** <!-- None / describe briefly -->
- **Platforms tested:** <!-- e.g., Linux (Wayland), Windows 11, macOS -->

## Mandatory Checklist

- [ ] This PR addresses **one single purpose** and is linked to an **approved Issue** (required for new features).
- [ ] I currently have **only 1 open PR** (this one) in this repository.
- [ ] This PR changes **<= 500 lines** (`additions + deletions`) and **<= 15 files** (or has maintainer pre-approval for `approved-large`).
- [ ] I added/updated automated tests in `tests/` and verified `QT_QPA_PLATFORM=offscreen pytest -q tests/` passes locally.
- [ ] I ran `ruff check` and `bandit -ll` on all modified Python files with zero new warnings or security issues.
- [ ] I updated the documentation/manuals (`README.md`, `docs/MANUAL.md`, `docs/manual/*.src.html` / `blindcue/help/manual_*.html`) in this PR, or justified below why no documentation update is needed.
- [ ] Verified cross-platform safety (Linux Wayland, Windows, macOS) and confirmed **no** telemetry, external network calls, or unjustified new dependencies.

**Documentation justification (only if no docs were updated):**
<!-- Explain why docs/manuals did not need updates, or remove this line if docs were updated. -->

## AI Assistance Disclosure

Select one option below:
- [ ] **No AI tools** were used to generate code or text in this PR.
- [ ] **AI tools were used**, and I have personally read, understood, simplified, and verified every modified line and test result.
