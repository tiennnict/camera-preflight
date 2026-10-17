# Decision Register

Single record of project decisions. Status values: **Confirmed** (maintainer approved), **Proposed** (awaiting maintainer approval), **Open** (no proposal yet or needs maintainer input), **Rejected**, **Superseded**.

To approve or reject a proposed item, change its status and add the date. Documents that depend on a Proposed item ([SRS.md](SRS.md), [TEST-CATALOGUE.md](TEST-CATALOGUE.md), [ARCHITECTURE.md](ARCHITECTURE.md), [UX.md](UX.md), [ROADMAP.md](ROADMAP.md)) are updated if it is rejected.

## 1. Confirmed (from handoff H§2 and this session)

| ID | Decision | Date | Source |
| --- | --- | --- | --- |
| D-01 | Personal, open-source project | before 2026-10-16 | H§2.1 |
| D-02 | Target user: individual buying a used camera | before 2026-10-16 | H§2.2 |
| D-03 | AF and metering reported as Suspect with confidence, not binary pass/fail | before 2026-10-16 | H§2.3 |
| D-04 | AF reported in two tiers; per-region sharpness map for mirrorless Sony | before 2026-10-16 | H§2.4 |
| D-05 | Maximum camera model coverage in the knowledge base | before 2026-10-16 | H§2.5 |
| D-06 | Guided manual mode is the fallback for anything not automatable | before 2026-10-16 | H§2.6 |
| D-07 | Project language English | before 2026-10-16 | H§2.7 |
| D-08 | GUI desktop application shipped as prebuilt releases | before 2026-10-16 | H§2.8 |
| D-09 | Python 3.12+ with PySide6; connection backends behind an interface | before 2026-10-16 | H§2.9 |
| D-10 | Repository name `camera-preflight`; Apache-2.0 | before 2026-10-16 | H§14 |
| D-11 | Open verification tasks are kept in docs, not opened as GitHub issues for now | 2026-10-16 | Session |
| D-12 | First work cycle produces documents only: SRS, technical solution, project structure, UI/UX design, development plan | 2026-10-16 | Session |
| D-13 | The assistant proposes optimisations, including features not in the handoff, for maintainer approval | 2026-10-16 | Session |
| D-14 | Everything published on GitHub is in English: code, comments, docs, commit messages, issues, pull requests, review replies, release notes. Clarifies D-07 | 2026-10-16 | Session |
| D-15 | The software is internationalised from the start; English and Vietnamese are built and kept complete in parallel. Confirms N-08 | 2026-10-16 | Session |
| D-17 | Approvals and decisions are requested from the maintainer in the chat, in Vietnamese, with enough context to decide; the English documents record the outcome | 2026-10-16 | Session |
| D-19 | Animations are layered vector SVG scenes driven by keyframe timelines, played in Qt Widgets through QGraphicsView; the same assets drive the HTML mockup and the printable field kit (static key frame) | 2026-10-16 | Session |
| D-20 | Animations use two generic body types (DSLR and mirrorless) without brand shapes or logos; the control involved is highlighted and named by a translatable label | 2026-10-16 | Session |
| D-21 | Camera menu settings (RAW, noise reduction off, lens corrections off) are given as text only, without animation, because menus differ per brand and generation | 2026-10-16 | Session |
| D-22 | The UI mockup covers every wizard step of all three profiles, one framed screen per step on a single page | 2026-10-16 | Session |
| D-23 | Two operating modes only: camera connected (tethered) or not connected (upload images). The app detects the driver and a plugged-in camera automatically. Supersedes the four entry choices in UX S1 | 2026-10-17 | Session |
| D-24 | Vendor SDK support is part of the design. A first-run setup step lets the user point to each SDK and explains the benefit of using it. Without an SDK, checks that need it are skipped automatically and reported as Not tested with the reason | 2026-10-17 | Session |
| D-25 | Tethered mode automates as much as possible: set camera settings and exposure parameters, release the shutter, download the files and analyse them. When an automatic command fails, the step falls back to guided manual instructions | 2026-10-17 | Session |
| D-26 | The wizard always contains every step. In upload mode, the capture control of each shooting step is replaced by an upload button | 2026-10-17 | Session |
| D-27 | The report delivered to the user is an HTML file | 2026-10-17 | Session |
| D-28 | No Quick, Standard or Full profiles. The wizard always shows every step that applies to the camera; the user may skip any step, which is then reported as Not tested (skipped by user). The planned number of shots is shown at the start | 2026-10-17 | Session |
| D-29 | Upload mode accepts images per step only; there is no bulk upload with automatic assignment to steps | 2026-10-17 | Session |
| D-30 | No remote pre-check pack and no printable field kit. Each shooting step shows the required shooting parameters, whoever takes the shots. On upload, the app checks that the parameters (aperture, exposure time, ISO, file type and so on) are sufficient for the test, and rejects frames that are not, with the reason (for example exposure too short) | 2026-10-17 | Session |
| D-31 | Vendor SDK integration is fully designed and implemented. The test environment downloads the SDKs to test against them. Release builds contain no SDK; the user is told where to download it and either places it in the default folder or points the app to another folder | 2026-10-17 | Session |
| D-32 | No time estimates, no shot-count estimates and no session history in the app | 2026-10-17 | Session |
| D-33 | Visual (manual) physical checks show real-world reference photos of each defect so the user can recognise it | 2026-10-17 | Session |
| D-34 | The wizard behaves like a diagnostics tool, ordered by automation level: (1) fully automatic checks first: run, mark the result and advance on their own; (2) semi-automatic checks next, either with a helper that detects the user's action and starts the check automatically, or, where detection is not possible, with a button the user presses; (3) fully manual checks last. Every action the PC can perform on the camera over USB is done by the app, never by the user | 2026-10-17 | Session |
| D-35 | A short visual blocker check (about 30 seconds, yes/no questions on severe defects only) runs at the very start, before any automatic check. All other manual checks stay last | 2026-10-17 | Session |
| D-36 | No session resume: every app launch starts a new session; an interrupted session is not continued | 2026-10-17 | Session |
| D-37 | The report keeps the camera's actual shutter count read before and after the session; the wizard shows no shot estimate or counter | 2026-10-17 | Session |
| D-38 | Reference photos come only from openly licensed sources, with author, licence and source recorded and shown in the app; target 4 photos per defect. The maintainer adds or replaces photos with their own where needed | 2026-10-17 | Session |
| D-18 | The wizard shows 2D animations that illustrate the physical actions the user must perform (for example plugging a cable, powering on, mounting a lens, fitting a body cap, pressing or holding a button, tilting the camera to inspect a part) | 2026-10-16 | Session |
| D-16 | The maintainer works with the assistant in Vietnamese. The assistant translates into English for GitHub and for the English UI text, and writes the Vietnamese UI text alongside | 2026-10-16 | Session |

## 2. Proposed (awaiting approval)

Design revisions and new features are detailed in [DESIGN-REVIEW.md](DESIGN-REVIEW.md).

| ID | Decision | Detail | Status |
| --- | --- | --- | --- |
| R-01 | AF tier 1 = focus not acquired or shutter not released within a timeout | DESIGN-REVIEW §3 | Proposed |
| R-02 | Quick profile runs entirely by file import; v0.1 has no USB dependency | DESIGN-REVIEW §3 | Superseded by D-23, D-28 (2026-10-17) |
| R-03 | Windows USB spike evaluates WPD first, then libusb, then .NET helper | DESIGN-REVIEW §3 | Proposed |
| R-04 | Standard profile: E1, E5, D5 by default; rest of E and full AF map in Full | DESIGN-REVIEW §3 | Superseded by D-28 (2026-10-17) |
| R-05 | C3 at maximum aperture; C2 relative to a slow reference speed | DESIGN-REVIEW §3 | Proposed |
| R-06 | B4 without lens rotation; sensor dust identified by f/22 versus f/8 | DESIGN-REVIEW §3 | Proposed |
| R-07 | Two-tier knowledge base (derived and curated); missing data never blocks a test | DESIGN-REVIEW §3 | Proposed |
| R-08 | Analysis on CFA arrays; RAW decoding isolated; DNG fallback | DESIGN-REVIEW §3 | Proposed |
| R-09 | JSON canonical report; self-contained HTML; SHA-256 evidence manifest | DESIGN-REVIEW §3 | Modified by D-27: HTML is the user deliverable; JSON stays internal to the session (2026-10-17) |
| R-10 | Shot and time budget planner over the three presets | DESIGN-REVIEW §3 | Superseded by D-28 (2026-10-17) |
| R-11 | Vendor SDK adapters outside the core repo until SDK terms are read | DESIGN-REVIEW §3 | Superseded by D-31 (2026-10-17) |
| R-12 | Package layout `src/camera_preflight/`; enforced layer dependencies | ARCHITECTURE §6 | Proposed |
| R-13 | No OpenCV in early milestones | ARCHITECTURE §2.2 | Proposed |
| R-14 | Single frame acceptance gate | TEST-CATALOGUE §1 | Proposed |
| R-15 | Record sensor temperature; robust per-ISO statistics | DESIGN-REVIEW §3 | Proposed |
| N-01 | Remote pre-check pack | DESIGN-REVIEW §4 | Rejected by D-30 (2026-10-17) |
| N-02 | Provenance and consistency checks | DESIGN-REVIEW §4 | Proposed |
| N-03 | Shutter count plausibility cross-check | DESIGN-REVIEW §4 | Proposed |
| N-04 | Automatic frame classification on import | DESIGN-REVIEW §4 | Superseded by D-29 (2026-10-17) |
| N-05 | Microphone-assisted burst rhythm | DESIGN-REVIEW §4 | Proposed |
| N-06 | Baseline and compare | DESIGN-REVIEW §4 | Proposed |
| N-07 | Field kit export | DESIGN-REVIEW §4 | Rejected by D-30 (2026-10-17) |
| N-08 | Bilingual UI (English, Vietnamese) | DESIGN-REVIEW §4 | Confirmed as D-15 (2026-10-16) |
| N-09 | Demo mode with synthetic session | DESIGN-REVIEW §4 | Proposed |
| N-10 | Shareable single-file report with hash manifest and re-verification | DESIGN-REVIEW §4 | Proposed |
| P-01 | Qt Widgets rather than Qt Quick (QML) | ARCHITECTURE §2.1 | Proposed |
| P-02 | All device backends run in a separate host process with a JSON protocol | ARCHITECTURE §2.3 | Proposed |
| P-03 | Tooling: uv, ruff, pyright, pytest, pytest-qt, hypothesis, import-linter | ARCHITECTURE §2.4 | Proposed |
| P-04 | gettext + Babel as the single translation catalogue | ARCHITECTURE §2.2 | Proposed |
| P-05 | Core libraries: rawpy, ExifTool, NumPy, SciPy, Pillow, pydantic, PyYAML, Jinja2 | ARCHITECTURE §2.2 | Proposed |
| P-06 | Release format: PyInstaller onedir zip (portable) with SHA256SUMS; installer later | ARCHITECTURE §2.4 | Proposed |
| P-07 | Release map v0.1 to v0.4 and milestones M0 to M5 | ROADMAP §2, §3 | Proposed |

## 3. Open (maintainer input needed)

| ID | Question | Needed by | Assistant's default if not decided |
| --- | --- | --- | --- |
| O-01 | Is Sony in the first release that includes USB control? | M4 | No: Sony via upload mode from v0.1; Sony USB in v0.4 |
| O-02 | Priority model list for KB seed (M3) and KB v1 (M5) | M3 | Ask the maintainer for the bodies they can physically test |
| O-03 | Code signing of Windows builds | v0.1 | Unsigned v0.1 with documented SmartScreen steps; revisit when downloads grow |
| O-04 | ExifTool bundled in releases or supplied by the user | v0.1 | Bundle if V-16 confirms it is allowed; else first-run download guidance |
| O-05 | Minimum Windows version | v0.1 | Windows 10 22H2 and Windows 11, x64 |
