# Guide for coding agents

camera-preflight is a Windows desktop diagnostics wizard, written in Python with PySide6, that checks a used camera before purchase. The upload-mode wizard and the connected-mode flow are implemented and tested without hardware; see [docs/WORK-PACKAGES.md](docs/WORK-PACKAGES.md) section 10 for what is done, partial or blocked. This file tells an agent (Claude Code or any other) how to work on it.

## 1. Read first, in this order

| Order | Document | Why |
| --- | --- | --- |
| 1 | [docs/DECISIONS.md](docs/DECISIONS.md) | What is binding (Confirmed) and what is not (Proposed) |
| 2 | [docs/WORK-PACKAGES.md](docs/WORK-PACKAGES.md) | What to build, in which order, and what blocks each package |
| 3 | [docs/SRS.md](docs/SRS.md) | Requirements; each package's acceptance criteria |
| 4 | [docs/TEST-CATALOGUE.md](docs/TEST-CATALOGUE.md) | Check procedures, analysis and verdict rules |
| 5 | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Technology, layers, package layout, dependency rules |
| 6 | [docs/UX.md](docs/UX.md) | Screens, interaction and copy rules, vocabulary |
| 7 | [docs/ROADMAP.md](docs/ROADMAP.md) | Milestones, exit criteria, Definition of Done |
| 8 | [docs/VERIFICATION.md](docs/VERIFICATION.md), [docs/LICENSING.md](docs/LICENSING.md), [docs/REFERENCE-IMAGES.md](docs/REFERENCE-IMAGES.md) | Open facts, legal limits, photo sources |

Do not implement from [docs/DESIGN-REVIEW.md](docs/DESIGN-REVIEW.md) or [docs/archive/handoff.md](docs/archive/handoff.md); they are historical.

## 2. Precedence when documents disagree

1. Confirmed decisions in DECISIONS.md.
2. SRS.
3. TEST-CATALOGUE (for check behaviour), ARCHITECTURE (for structure), UX (for screens and text).
4. ROADMAP and WORK-PACKAGES (for order and scope of a package).
5. The mockup (layout and flow only, D-45).

If two sources at the same level disagree, or a document contradicts a Confirmed decision, stop and report it. Do not pick one silently.

## 3. Decisions and approvals

- Only **Confirmed** items bind. **Proposed** items are not approved, even though they are written down (D-17). A package blocked by a Proposed item does not start, and no alternative is built in its place.
- The maintainer reads Vietnamese only. Any question or approval for the maintainer is asked in the chat, in Vietnamese, with enough context to answer without opening a document. The outcome is then recorded in English in DECISIONS.md.
- Never change a Confirmed item on your own. A finding that contradicts one is reported.

## 4. Language

- Everything on GitHub is in English: code, comments, docs, commit messages, branch names, pull requests, review replies (D-14).
- The only Vietnamese text in the repository is the translation catalogue `src/camera_preflight/locale/vi/` and the Vietnamese column of vocabulary tables.
- Every user-visible string (GUI, messages, report) goes through gettext and gets an English source text and a Vietnamese translation in the same change (D-15). Use the vocabulary in [docs/UX.md](docs/UX.md) section 9.1.
- On-screen text is short and complete in meaning, with no long notes or explanations (D-44). Follow the limits in [docs/UX.md](docs/UX.md) section 9. Do not copy text from the mockup.

## 5. Evidence and honesty

- Keep the labels `[Sourced]`, `[Inference]`, `[Guess]`, `[Unverified]` (meaning in [docs/archive/handoff.md](docs/archive/handoff.md) section 0) in code comments, docs and reports. Never present an inference, guess or unverified item as fact.
- Every threshold is a named parameter with its label; none is hard-coded in analysis code.
- No check reports Pass unless it ran on the required accepted frames (NFR-01). When in doubt, the result is Not tested with a reason.
- Nothing has been tested on a real camera. Hardware results go into `docs/hardware-log/`, one file per body and session.

## 6. Hard rules

- No vendor SDK files (binaries, headers, samples) in the repository, source archives or CI builds, ever (D-31, D-47). The maintainer's locally built binary release may bundle SDK runtime files through `packaging/package.py --with-sdk`; agents never publish it. SDKs are loaded at runtime from the bundled folder or the folder the user sets.
- No network access in the app, no telemetry (NFR-06).
- No personal metadata stored, logged or reported; only files the user selects are imported (FR-META-02, FR-ACQ-02).
- No buy or price advice, and no single score (FR-REP-05, FR-VER-02).
- No time estimate, shot estimate, shot counter, session history or resume (D-32, D-36).
- In connected mode, never ask the user to do what the app can do over USB (NFR-18).
- Layer dependencies follow [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) section 6; only `gui` imports PySide6.

## 7. Working on a package

1. Pick a package from WORK-PACKAGES.md whose dependencies are merged and whose blockers are approved.
2. Branch `wp/<id>-<short-name>` from `main`.
3. Implement only the package scope. Note anything out of scope in the pull request instead of building it.
4. Meet the Definition of Done ([docs/ROADMAP.md](docs/ROADMAP.md) section 6): lint, type check, import contracts, tests, both translations, labelled parameters, docs updated.
5. Commit with Conventional Commits. Open a pull request whose description lists the package ID, the requirements covered and how each is verified, and any verification task it advanced.
6. If a verification task is answered, update [docs/VERIFICATION.md](docs/VERIFICATION.md) with the result, the date and the source.
