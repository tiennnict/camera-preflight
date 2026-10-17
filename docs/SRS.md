# Software Requirements Specification: camera-preflight

| Field | Value |
| --- | --- |
| Document | SRS |
| Version | 0.3 (revised after maintainer decisions D-23 to D-45, 2026-10-17) |
| Status | Draft. Items that depend on a Proposed decision are binding only once approved in [DECISIONS.md](DECISIONS.md) |
| Baseline | [archive/handoff.md](archive/handoff.md) (`H§n`), [DESIGN-REVIEW.md](DESIGN-REVIEW.md) |
| Related | [TEST-CATALOGUE.md](TEST-CATALOGUE.md), [ARCHITECTURE.md](ARCHITECTURE.md), [UX.md](UX.md), [ROADMAP.md](ROADMAP.md), [VERIFICATION.md](VERIFICATION.md), [LICENSING.md](LICENSING.md), [REFERENCE-IMAGES.md](REFERENCE-IMAGES.md) |

## 1. Introduction

### 1.1 Purpose

This document specifies what camera-preflight shall do and the qualities it shall have. It is the reference for design, implementation, testing and acceptance of each release.

### 1.2 Product scope

camera-preflight is a desktop diagnostics tool that helps an individual evaluate a used digital camera. With the camera connected over USB, it runs as many checks as possible by itself; with no camera connected, it guides the user to shoot with given parameters and analyses the uploaded images. It produces an evidence-based HTML report of suspected issues. It does not recommend whether to buy or at what price.

### 1.3 Conventions

- **shall** = mandatory; **should** = recommended; **may** = optional.
- Priority: **M** Must, **S** Should, **C** Could (MoSCoW).
- Release: target release from [ROADMAP.md](ROADMAP.md) (`v0.1` to `v0.4`, `later`).
- Source: `H§n` handoff section, `R-xx`/`N-xx` design review item, `D-xx` decision.
- Evidence labels `[Sourced]`, `[Inference]`, `[Guess]`, `[Unverified]` keep the meaning defined in H§0. A requirement that depends on an unverified fact names the verification task (`V-xx`).

### 1.4 Definitions

| Term | Meaning |
| --- | --- |
| Mode | Connected (camera controlled over USB) or Upload (user uploads images per step) (D-23) |
| Session | One evaluation of one camera body, from launch to report; not resumable (D-36) |
| Phase | Group of checks by automation level: start, blocker check, automatic, semi-automatic, manual, results (D-34, D-35) |
| Check | One test from the catalogue (A1 to F) |
| Helper | A watcher that detects a user's physical action (for example body cap fitted) and starts a semi-automatic check |
| Frame | One image file plus its decoded CFA data, metadata and provenance |
| CFA | Colour filter array: the raw sensor mosaic before demosaicing |
| Path | How a check was executed: automatic, semi-automatic, from uploaded files, manual |
| Result level | Pass, Suspect, Fail, Not tested |
| Confidence | High, Medium, Low; attached to every result except Not tested |
| Severity | Blocker, High, Medium, Low; attached to Suspect and Fail results |
| Acceptance gate | The component that accepts or rejects a frame before analysis |
| Knowledge base (KB) | Model data: derived tier (from the user's own frames) and curated tier (sourced YAML) |
| Backend | A connection implementation: standard PTP, vendor SDK adapter |
| Reference photo | A real, openly licensed photo of a defect shown in a visual check (D-33, D-38) |

## 2. Overall description

### 2.1 Product perspective

Standalone, offline desktop application. It talks to cameras over USB through interchangeable backends (standard PTP and vendor SDK adapters), or works from uploaded image files. Vendor SDKs are not shipped; the user downloads them and the app loads them at runtime (D-31).

### 2.2 Product functions (summary)

1. On first run, let the user point to vendor SDKs and explain what each adds (D-24).
2. Detect the camera and its driver; choose connected or upload mode (D-23).
3. Run a short visual blocker check (D-35).
4. Run automatic checks unattended; then semi-automatic checks, started by helpers or by a button; then manual checks with reference photos (D-34).
5. In connected mode, perform every camera action possible over USB; fall back to guided manual steps when a command fails (D-25).
6. In upload mode, show the shooting parameters per step, accept uploads per step, and validate them (D-26, D-29, D-30).
7. Analyse frames, assign result level, confidence and severity; never report Pass for a check that did not run.
8. Produce a self-contained HTML report (D-27).

### 2.3 Users

| Class | Description | Primary needs |
| --- | --- | --- |
| U1 Buyer with the camera at hand | At the seller's place or at home; may or may not have a cable and PC | Fast automatic checks, clear guidance for physical actions, honest results |
| U2 Buyer with images from a seller | Seller shoots with the shown parameters and sends files | Upload mode with clear parameters and validation |
| U3 KB contributor | Adds model data, known issues or reference photos by pull request | Schema, validation tool, attribution rules |

### 2.4 Operating environment

- OS: Windows 10 22H2 and Windows 11, x64 only (D-43). macOS and Linux later; design must not preclude them.
- Hardware: PC with USB 2.0 or newer; 8 GB RAM recommended `[Guess]`; optional microphone (N-05).
- Cameras: Canon, Sony and Nikon. Upload mode supports all three from v0.1; connected mode supports Canon and Sony from v0.2 and Nikon from v0.4 (D-39). Every model of these brands is in scope; there is no priority model list (D-40).
- No network connection required for any function.

### 2.5 Constraints

| ID | Constraint | Source |
| --- | --- | --- |
| CON-01 | Python 3.12 or newer; PySide6 GUI | D-09 |
| CON-02 | Apache-2.0 for project code; LGPL libraries kept replaceable (onedir distribution) | H§10 |
| CON-03 | The repository, source archives and CI builds contain no vendor SDK files. The maintainer's locally built binary release may bundle them; without them SDK features are Not tested with the reason | D-31, D-47 |
| CON-04 | Everything published on GitHub in English | D-07, D-14 |
| CON-05 | No reading, storing or transmitting of previous-owner personal data from the camera | H§10 |
| CON-06 | No brand names in the product name | H§10 |
| CON-07 | Internationalised from the start; English and Vietnamese complete in every release | D-15 |
| CON-08 | Reference photos only from openly licensed sources or the maintainer's own photos, with attribution | D-38 |

### 2.6 Assumptions and dependencies

| ID | Assumption | Risk if false | Verification |
| --- | --- | --- | --- |
| AS-01 | LibRaw (via rawpy) decodes RAW files of the priority models | Checks fall back to DNG or JPEG with lower confidence | V-14 |
| AS-02 | ExifTool decodes maker notes needed for A3, A6, D, and may be bundled | Fields reported as unreadable; if bundling is not allowed, an in-house reader is written (D-42) | V-16 |
| AS-03 | Focus priority prevents shutter release without focus | AF tier 1 logic revised per brand | V-15 |
| AS-04 | A PTP path from Windows without driver replacement exists (WPD) | Connected mode needs a driver step or a .NET helper | V-13 |
| AS-05 | Live view and properties needed by helpers H1 to H7 are readable on target bodies | Helpers fall back to the button | V-22 |
| AS-06 | The test environment can obtain vendor SDKs | SDK tests run only on the maintainer's machine | V-23 |

### 2.7 Out of scope

Buy or price advice; absolute shutter speed measurement (C5); internal service logs; Wi-Fi transport; mobile app; cloud services; repair guidance; time or shot estimates; session history and resume (D-32, D-36); remote packs and printable field kits (D-30).

## 3. Functional requirements

### 3.1 Session (SES)

| ID | Requirement | Pri | Release | Source |
| --- | --- | --- | --- | --- |
| FR-SES-01 | Each launch shall start a new session in its own folder containing frames, results and report. | M | v0.1 | H§5, D-36 |
| FR-SES-03 | The system shall record the user-entered body serial (optional) and the serial read from the camera or metadata. | M | v0.1 | H§6 A1 |
| FR-SES-04 | The system shall store frames as copies; it shall never modify or delete files on the camera or the source card. | M | v0.1 | H§5 |
| FR-SES-07 | The HTML report shall embed evidence images only, never original frame files, because those may contain personal fields written by the camera. | M | v0.1 | NFR-07, D-27 |
| FR-SES-08 | The system shall not show a list of past sessions and shall not resume an interrupted session. | M | v0.1 | D-32, D-36 |

### 3.2 Start, SDK and detection (CON)

| ID | Requirement | Pri | Release | Source |
| --- | --- | --- | --- | --- |
| FR-CON-01 | The system shall continuously detect a camera and its driver on USB and choose connected mode when one is found, upload mode otherwise; the user may switch to upload mode at any time. | M | v0.2 | D-23 |
| FR-CON-02 | The system shall define a backend interface covering: device info, session open and close, storage, object transfer, property get and set, live view, capture, focus drive, AF point selection, capability query. | M | v0.2 | H§5 |
| FR-CON-03 | The system shall select, per camera, the most capable backend available: configured SDK adapter, then standard PTP. | M | v0.2 | D-24 |
| FR-CON-04 | The system shall show the required USB mode and conflicting settings for the detected brand before connecting. | M | v0.2 | H§6 `[Sourced]` |
| FR-CON-05 | The default Windows path shall not require replacing the OS camera driver; if a driver change is needed, the system shall explain it and how to revert it. | M | v0.2 | R-03, V-13 |
| FR-CON-06 | On first run and in Settings, the system shall let the user set a folder per vendor SDK, show the default folder, say where to download the SDK, and describe what the SDK adds for that brand. | M | v0.2 | D-24, D-31 |
| FR-CON-07 | Checks that need an SDK that is not configured shall be skipped automatically and reported as Not tested, reason "SDK not configured". | M | v0.2 | D-24 |
| FR-CON-08 | When a backend fails during a session, the system shall offer to reconnect or switch to upload mode, and record the reason. | M | v0.2 | H§5 |
| FR-CON-09 | In upload mode the system shall identify brand and model from the first uploaded frame's metadata. | M | v0.1 | D-23 |

### 3.3 Automation and acquisition (ACQ)

| ID | Requirement | Pri | Release | Source |
| --- | --- | --- | --- | --- |
| FR-ACQ-05 | In connected mode the system shall perform every camera action possible over USB itself: apply settings and exposure parameters, select AF points, drive focus, release the shutter, download files. | M | v0.2 | D-25, D-34 |
| FR-ACQ-06 | Before changing a camera setting the system shall record its original value, and offer to restore all changed settings at session end. | M | v0.2 | new |
| FR-ACQ-09 | When an automatic command fails, the system shall retry once, then turn that item into a guided manual step and continue automatically once the user confirms. | M | v0.2 | D-25 |
| FR-ACQ-10 | The system shall provide helpers H1 to H7 ([UX.md](UX.md) section 3.3) that detect a user's physical action and start the related checks automatically. | M | v0.2 | D-34 |
| FR-ACQ-11 | When a helper cannot run on a body, or detects nothing within a time limit, the system shall offer a button that starts the checks; the helper keeps watching. | M | v0.2 | D-34, V-22 |
| FR-ACQ-12 | Checks that share a set-up shall run as one group after a single helper trigger. | S | v0.2 | D-34 |
| FR-ACQ-01 | In upload mode each shooting step shall show the required parameters and an upload button, and accept files for that step only. | M | v0.1 | D-26, D-29 |
| FR-ACQ-02 | The system shall import only files the user selects for a step; it shall never import other files from a card. | M | v0.1 | CON-05, D-29 |
| FR-ACQ-08 | The system may record audio during burst checks and detect shutter onsets. | C | later | N-05 |

### 3.4 Frame acceptance and provenance (GATE)

| ID | Requirement | Pri | Release | Source |
| --- | --- | --- | --- | --- |
| FR-GATE-01 | The system shall check every frame against its check's requirements before analysis: aperture, exposure time, ISO, file type, noise reduction, focus mode, histogram range, clipping, flicker, selected AF point. | M | v0.1 | R-14, D-30 |
| FR-GATE-02 | A rejected frame shall be kept as evidence, excluded from analysis, and shown with a plain reason and the value needed (for example "exposure 1/60 s is too short; use 30 s"). | M | v0.1 | D-30 |
| FR-GATE-03 | In connected mode the system shall re-shoot automatically after a rejection; in upload mode it shall ask for a new upload. | M | v0.1 | R-14 |
| FR-GATE-04 | The system shall check that all frames come from the same body and match the user-entered serial when provided. | M | v0.1 | N-02 |
| FR-GATE-06 | The system shall flag frames whose metadata indicates editing software or missing maker notes. | S | v0.1 | N-02 |
| FR-GATE-07 | When provenance cannot be determined, the system shall lower the confidence of dependent results and state why. | M | v0.1 | N-02 |

### 3.5 Metadata and RAW decoding (META)

| ID | Requirement | Pri | Release | Source |
| --- | --- | --- | --- | --- |
| FR-META-01 | The system shall decode RAW frames to CFA arrays with black level, white level and CFA pattern. | M | v0.1 | R-08 |
| FR-META-02 | The system shall read metadata through a versioned allowlist and shall not store, log or report personal fields. | M | v0.1 | NFR-07 |
| FR-META-03 | When a RAW format cannot be decoded, the system shall explain the DNG conversion option and accept DNG. | S | v0.1 | R-08, V-14 |
| FR-META-04 | JPEG input is accepted only for checks that declare JPEG support, with confidence capped at Low. | S | v0.1 | R-08 |
| FR-META-05 | The system shall record sensor or camera temperature when metadata exposes it. | S | v0.2 | R-15 |

### 3.6 Wizard and checks (TST)

Detailed procedures, analysis and verdict rules: [TEST-CATALOGUE.md](TEST-CATALOGUE.md).

| ID | Requirement | Pri | Release | Source |
| --- | --- | --- | --- | --- |
| FR-TST-01 | Each check shall declare: ID, group, automation level per mode (automatic, semi-automatic with helper, semi-automatic with button, manual), required frames, gate rules, backend capabilities and SDK needs, KB fields. | M | v0.1 | H§5, D-34 |
| FR-TST-02 | Each check shall produce a result with level, confidence, severity (when Suspect or Fail), path, evidence, and a plain explanation. | M | v0.1 | H§5 |
| FR-TST-03 | A check that did not run, or ran with insufficient accepted frames, shall be Not tested with a reason; never Pass. | M | v0.1 | H§5 |
| FR-TST-04 | AF and metering checks shall not report Fail from a single lens or repetition; they report Suspect with confidence. | M | v0.1 | D-03 |
| FR-TST-05 | Checks shall prefer relative comparisons; every absolute threshold is a named parameter with its evidence label. | M | v0.1 | H§5 |
| FR-TST-06 | AF tier 1 shall be determined from focus failure or shutter non-release (timeout or user report). | M | v0.1 | R-01, V-15 |
| FR-TST-07 | Manual checks shall record the user's level, notes and optional photo, path = manual. | M | v0.1 | H§6 F |
| FR-TST-08 | The wizard shall contain every check that applies to the body, with no profiles; the user may skip any check (Not tested, "skipped by user"). | M | v0.1 | D-26, D-28 |
| FR-TST-09 | The wizard shall run phases in this order: start, blocker check, automatic, semi-automatic, manual, results. | M | v0.1 | D-34, D-35 |
| FR-TST-10 | Automatic checks shall run, set their own result and advance without user input; the user can pause or skip. | M | v0.2 | D-34 |
| FR-TST-11 | The blocker check shall ask only about severe visible defects, take about 30 seconds, and offer to stop when a Blocker is found. | M | v0.1 | D-35 |

### 3.7 Verdict (VER)

| ID | Requirement | Pri | Release | Source |
| --- | --- | --- | --- | --- |
| FR-VER-01 | The system shall assign severity Blocker, High, Medium or Low to each Suspect or Fail result using rules per check. | M | v0.1 | H§9 |
| FR-VER-02 | The system shall not compute a single aggregate score. | M | v0.1 | H§9 |
| FR-VER-04 | A known issue from the curated KB shall raise the priority of its confirming check and show a warning; it never by itself produces Suspect or Fail. | M | v0.3 | H§9 |

### 3.8 Report (REP)

| ID | Requirement | Pri | Release | Source |
| --- | --- | --- | --- | --- |
| FR-REP-02 | The system shall produce one self-contained HTML report, viewable offline and printable. | M | v0.1 | D-27 |
| FR-REP-03 | The report shall contain: counts per result level; Blockers first; camera info (brand, model, serial suffix, firmware, shutter count before and after the session, lens); results per check with confidence and path; evidence images; Not tested list with reasons; points to ask the seller about. | M | v0.1 | H§9, D-37 |
| FR-REP-04 | The report shall include SHA-256 of every source frame and evidence image; it shall not claim tamper evidence. | M | v0.1 | R-09 |
| FR-REP-05 | The report shall not contain buy advice, price advice or an overall pass or fail of the camera. | M | v0.1 | H§9 |
| FR-REP-06 | The report shall state the app version, KB version, parameter set and evidence labels of thresholds used. | M | v0.1 | H§0 |
| FR-REP-07 | The report shall show shutter count plausibility checks with their basis. | S | v0.2 | N-03 |
| FR-REP-09 | Structured result data shall be kept inside the session folder for re-analysis; it is not a user-facing export. | M | v0.1 | D-27 |

### 3.9 Knowledge base (KB)

| ID | Requirement | Pri | Release | Source |
| --- | --- | --- | --- | --- |
| FR-KB-01 | The system shall load curated KB entries from versioned YAML validated against a schema. | M | v0.3 | H§9 |
| FR-KB-02 | Each curated entry and known issue shall carry a source and confidence. | M | v0.3 | H§9 |
| FR-KB-03 | The system shall build a derived model record from the session's own frames, separate from curated data. | M | v0.1 | R-07 |
| FR-KB-04 | A missing curated entry shall lower confidence or mark individual checks Not tested ("no reference data"); it never blocks a check. | M | v0.1 | R-07 |
| FR-KB-05 | If the AF metadata decoder is not verified for a model, metadata-based AF point confirmation shall be skipped and stated. | M | v0.3 | H§9 |
| FR-KB-06 | The repository shall provide a KB validation command for CI and contributors. | M | v0.3 | H§9 |

### 3.10 Guidance (GUI)

| ID | Requirement | Pri | Release | Source |
| --- | --- | --- | --- | --- |
| FR-GUI-01 | Every step that needs the user shall show what to do and what to expect; in upload mode, the exact shooting parameters. | M | v0.1 | H§1, D-30 |
| FR-GUI-03 | The system shall provide solid-colour images (red, green, blue, white, black) for LCD and EVF checks, and copy them to the card when connected. | S | v0.1 | H§6 F |
| FR-GUI-05 | The system shall provide a demo session generated from synthetic frames. | C | v0.1 | N-09 |
| FR-GUI-06 | Every step that requires a physical action shall show a looping 2D animation, text-free, pausable, with a static frame under reduced motion. | M | v0.1 | D-18 to D-21 |
| FR-GUI-07 | Visual checks (blocker and manual) shall show up to 4 reference photos per defect with author, licence and source. | M | v0.1 | D-33, D-38 |
| FR-GUI-08 | The system shall show no time estimate, no shot estimate and no shot counter. | M | v0.1 | D-32 |
| FR-GUI-09 | On-screen text shall be short and complete in meaning, following the copy rules in [UX.md](UX.md) section 9; long notes and explanations are shown only on demand. | M | v0.1 | D-44 |

### 3.11 Settings (SET)

| ID | Requirement | Pri | Release | Source |
| --- | --- | --- | --- | --- |
| FR-SET-01 | The user shall be able to choose UI language (English, Vietnamese); default follows the OS, else English. | M | v0.1 | D-15 |
| FR-SET-02 | The user shall be able to set the sessions folder and the SDK folders (FR-CON-06). ExifTool is bundled and needs no setting (D-42). | M | v0.1 | D-24, D-42 |
| FR-SET-03 | The user shall be able to choose light or dark theme (default: OS) and reduced motion. | C | v0.1 | UX |

### 3.12 Withdrawn requirements

| ID | Withdrawn by |
| --- | --- |
| FR-SES-02 (save and resume), FR-SES-05 (open completed session), FR-SES-06 (compare with baseline) | D-36, D-32 |
| FR-ACQ-03, FR-ACQ-04 (bulk import and classification) | D-29 |
| FR-ACQ-07 (shot counter) | D-32 |
| FR-PLN-01 to 05 (profiles, budgets, plan screen) | D-28, D-32 |
| FR-KIT-01 to 04 (field kit, remote pack, printable AF chart as export) | D-30 |
| FR-VER-03 (stop recommendation after early phases): replaced by FR-TST-11 | D-35 |
| FR-VER-05 (remote-pack confidence cap) | D-30 |
| FR-REP-01 (JSON as canonical user deliverable), FR-REP-08 (re-verification feature): data kept internally by FR-REP-09 | D-27 |
| FR-GATE-05 (import window) | D-29 |
| FR-GUI-04 (preparation list for a plan) | D-28 |

## 4. External interface requirements

### 4.1 User interface

Specified in [UX.md](UX.md): diagnostics-style wizard with a persistent list of phases and checks, live status, result levels with colour, icon and text, keyboard operable, usable at 1280 x 720 `[Guess]`.

### 4.2 Hardware interfaces

- USB camera connection through the OS camera stack or a user-supplied vendor SDK.
- Optional microphone (N-05, later).

### 4.3 Software interfaces

| Interface | Use | Notes |
| --- | --- | --- |
| LibRaw via rawpy | RAW decoding | Bundled; LGPL-2.1 replaceable (onedir) |
| ExifTool | Metadata and maker notes | Bundled, run as a subprocess behind a metadata reader interface; replaced by an in-house reader if V-16 rules out bundling (D-42) |
| Vendor SDKs | Adapters for Canon, Nikon, Sony | User-supplied at runtime; downloaded by the test environment for development (D-31) |
| OS camera stack (WPD on Windows) | PTP transport | Subject to V-13 |

### 4.4 File formats

| Format | Direction | Notes |
| --- | --- | --- |
| CR2, CR3, NEF, ARW, DNG | In | As supported by bundled LibRaw (V-14) |
| JPEG | In | Limited checks, Low confidence |
| `report.html` | Out | The user deliverable (D-27) |
| Session data (JSON) | Internal | Results and metadata for re-analysis |
| PNG | Out | Evidence images, solid-colour test images |
| KB YAML | In | Curated tier |

## 5. Non-functional requirements

| ID | Category | Requirement | Pri | Verification |
| --- | --- | --- | --- | --- |
| NFR-01 | Correctness | No result shall be Pass unless the check ran on the required accepted frames. | M | Unit tests |
| NFR-02 | Correctness | On the synthetic defect suite, B1 to B4 shall detect at least 95% of injected defects with no more than 1 false defect per 10 megapixels `[Guess]`; recalibrated on real cameras (V-07). | M | Automated test |
| NFR-03 | Performance | Analysis of one 24-megapixel RAW frame for B1 or B2 should complete within 5 s on a 4-core PC `[Guess]`. | S | Benchmark |
| NFR-04 | Responsiveness | The GUI shall stay responsive during capture, transfer and analysis. | M | pytest-qt, manual |
| NFR-05 | Reliability | Unplugging the camera shall not lose frames or results already obtained in the running session. | M | Test |
| NFR-06 | Privacy | The app shall make no network requests by default. | M | Network-off test |
| NFR-07 | Privacy | The app shall not read personal settings from the camera or store personal metadata fields (FR-META-02); it imports only files the user selects (FR-ACQ-02). | M | Inspection, test |
| NFR-08 | Transparency | Every threshold, parameter set and KB entry used shall be traceable from the report. | M | Inspection |
| NFR-09 | Portability | Windows build shall run from an unpacked folder without administrator rights. Builds are not code-signed (D-41); the README explains the SmartScreen prompt. | M | Release test |
| NFR-10 | Portability | Platform-specific code shall be confined to backends and packaging. | M | Import contract |
| NFR-11 | Maintainability | Analysis and verdict modules shall have at least 90% line coverage `[Guess]`. | S | CI |
| NFR-12 | Maintainability | Layer dependency rules ([ARCHITECTURE.md](ARCHITECTURE.md) section 6) enforced in CI. | M | CI |
| NFR-13 | Licensing | Releases ship LICENSE, NOTICE, third-party licence texts and reference photo attributions; no vendor SDK files. | M | Release checklist |
| NFR-14 | Localisation | All user-visible strings (GUI, messages, report) translatable; English and Vietnamese 100% complete in every release. | M | CI check |
| NFR-15 | Accessibility | Result levels never conveyed by colour alone; text contrast WCAG 2.1 AA. | M | Review |
| NFR-16 | Security | No code execution from session or KB files; YAML safe loading. | M | Inspection, test |
| NFR-17 | Size | Windows release archive should stay under 250 MB `[Guess]`. | C | CI |
| NFR-18 | Automation | In connected mode, no step shall ask the user to do something the backend can do over USB. | M | Review per check, usability test |

## 6. Data requirements

### 6.1 Session folder

```
<sessions>/<yyyymmdd-hhmmss>-<model>-<serial-suffix>/
  session.json        identity, mode, backend, settings snapshot, versions
  frames/             copied originals, never modified
  frames.json         per-frame allowlisted metadata, gate result, SHA-256
  evidence/           generated maps and charts (PNG)
  results.json        per-check results
  report.html         the report
```

### 6.2 Retention

Sessions stay on disk until the user deletes the folder. The app does not list them (D-32).

### 6.3 Schemas

Result and KB schemas are defined in [ARCHITECTURE.md](ARCHITECTURE.md) section 5 and versioned with SemVer.

## 7. Verification approach

| Method | Used for |
| --- | --- |
| Test (automated) | Analysis, verdict, gate, helpers on recorded live view, schemas, report rendering |
| Demonstration | Wizard flows, connected mode on real cameras (hardware test protocol in [ROADMAP.md](ROADMAP.md)) |
| Inspection | Privacy, licensing, attributions, traceability, accessibility |
| Analysis | Threshold calibration against real-camera data (V-07) |

## 8. Traceability (summary)

| Requirement group | Sources | Checks |
| --- | --- | --- |
| SES | H§5, D-32, D-36 | All |
| CON | H§4, H§6, D-23, D-24, D-31 | A1 to A5, all connected checks |
| ACQ | H§5, D-25, D-26, D-29, D-34 | B, C, D, E |
| GATE | H§6, R-14, N-02, D-30 | All shooting checks |
| META | H§5, R-08, R-15 | A3, A6, B, D |
| TST | H§5, H§6, R-01, D-28, D-34, D-35 | A to F |
| VER | H§9 | All |
| REP | H§9, D-27, D-37 | All |
| KB | H§9, R-07 | A3, A4, D1, D9 |
| GUI | D-18 to D-21, D-32, D-33, D-38, D-44 | Physical and visual steps |
