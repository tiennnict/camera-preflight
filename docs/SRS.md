# Software Requirements Specification: camera-preflight

| Field | Value |
| --- | --- |
| Document | SRS |
| Version | 0.1 (draft for maintainer review) |
| Status | Draft. Requirements from proposed revisions (`R-xx`, `N-xx`) are binding only once approved in [DECISIONS.md](DECISIONS.md) |
| Baseline | [archive/handoff.md](archive/handoff.md) (`H§n`), [DESIGN-REVIEW.md](DESIGN-REVIEW.md) |
| Related | [TEST-CATALOGUE.md](TEST-CATALOGUE.md), [ARCHITECTURE.md](ARCHITECTURE.md), [UX.md](UX.md), [ROADMAP.md](ROADMAP.md), [VERIFICATION.md](VERIFICATION.md), [LICENSING.md](LICENSING.md) |

## 1. Introduction

### 1.1 Purpose

This document specifies what camera-preflight shall do and the qualities it shall have. It is the reference for design, implementation, testing and acceptance of each release.

### 1.2 Product scope

camera-preflight is a desktop wizard that helps an individual evaluate a used digital camera before or shortly after buying it. It guides the user through test shots, acquires or imports the images, analyses them, and produces an evidence-based report of suspected issues. It does not recommend whether to buy or at what price.

### 1.3 Conventions

- **shall** = mandatory; **should** = recommended; **may** = optional.
- Priority: **M** Must, **S** Should, **C** Could (MoSCoW).
- Release: target release from [ROADMAP.md](ROADMAP.md) (`v0.1` to `v0.5`, `later`).
- Source: where the requirement comes from (`H§n` handoff section, `R-xx`/`N-xx` design review item, `D-xx` decision).
- Evidence labels `[Sourced]`, `[Inference]`, `[Guess]`, `[Unverified]` keep the meaning defined in H§0. A requirement that depends on an unverified fact names the verification task (`V-xx`).

### 1.4 Definitions

| Term | Meaning |
| --- | --- |
| Session | One evaluation of one camera body: plan, frames, results, report, stored in one folder |
| Plan | The ordered list of tests selected for a session, with shot and time estimates |
| Profile | A preset plan: Quick, Standard, Full |
| Frame | One image file plus its decoded CFA data, metadata and provenance |
| CFA | Colour filter array: the raw sensor mosaic before demosaicing |
| Path | How a test was executed: automatic (tethered), semi-automatic (user acts, app reads the image), file import, manual |
| Result level | Pass, Suspect, Fail, Not tested |
| Confidence | High, Medium, Low; attached to every result except Not tested |
| Severity | Blocker, High, Medium, Low; attached to Suspect and Fail results |
| Acceptance gate | The component that accepts or rejects a frame before analysis |
| Knowledge base (KB) | Model data: derived tier (from the user's own frames) and curated tier (sourced YAML) |
| Backend | A connection implementation: PTP, vendor SDK adapter, file import |
| Remote pack | A shooting script sent to a seller, whose returned files are analysed by the buyer |

## 2. Overall description

### 2.1 Product perspective

Standalone, offline desktop application. It talks to cameras over USB through interchangeable backends, or works entirely from image files. Vendor SDKs, when used, are supplied by the user and loaded at runtime (H§10, R-11).

### 2.2 Product functions (summary)

1. Create a session and identify the camera (from USB or from image metadata).
2. Plan tests within a shot and time budget.
3. Guide the user through preparation, shooting and manual checks.
4. Acquire frames by tethered capture or import; classify, validate and check provenance.
5. Analyse frames per test (groups A to F, [TEST-CATALOGUE.md](TEST-CATALOGUE.md)).
6. Assign result level, confidence and severity; never report Pass for a test that did not run.
7. Produce a JSON record and a self-contained HTML report with evidence and integrity hash.
8. Export field kit and remote pack; compare a session with a baseline.

### 2.3 User classes

| Class | Description | Primary needs |
| --- | --- | --- |
| U1 On-site buyer | Inspects a camera at the seller's place; 15 to 30 minutes `[Guess]`; may not have a laptop on site | Quick profile, field kit, fast import and verdict |
| U2 Remote buyer | Buys online; seller supplies frames | Remote pack, provenance checks, clear confidence limits |
| U3 Home tester | Has received the camera; return window; has tripod and time | Standard or Full profile, tethered capture, full report, compare later |
| U4 KB contributor | Adds model data or known issues by pull request | Schema, validation tool, contribution rules |

Detailed personas and journeys: [UX.md](UX.md).

### 2.4 Operating environment

- OS: Windows 10 and 11 x64 (first target). macOS and Linux: later releases, design must not preclude them.
- Hardware: PC with USB 2.0 or newer; 8 GB RAM recommended `[Guess]`; optional microphone (N-05).
- Cameras: Canon and Nikon required; Sony optional (open decision O-01 in [DECISIONS.md](DECISIONS.md)).
- No network connection required for any function.

### 2.5 Constraints

| ID | Constraint | Source |
| --- | --- | --- |
| CON-01 | Python 3.12 or newer; PySide6 GUI | D-09 |
| CON-02 | Apache-2.0 for project code; LGPL libraries kept replaceable (onedir distribution) | H§10 |
| CON-03 | No vendor SDK binaries, headers or SDK-derived bindings in the repository or releases until V-01 is resolved | H§10, R-11 |
| CON-04 | Everything published on GitHub (code, comments, docs, commits, issues, pull requests, release notes) in English | D-07, D-14 |
| CON-07 | Internationalised from the start; English and Vietnamese UI and report text complete in every release | D-15 |
| CON-05 | No reading, storing or transmitting of previous-owner personal data from the camera | H§10 |
| CON-06 | No brand names in the product name | H§10 |

### 2.6 Assumptions and dependencies

| ID | Assumption | Risk if false | Verification |
| --- | --- | --- | --- |
| AS-01 | LibRaw (via rawpy) decodes RAW files of the priority models | B tests fall back to DNG or JPEG with lower confidence | V-14 |
| AS-02 | ExifTool decodes maker notes needed for A3, A6, D, N-02 | Fields reported as unreadable | V-16 |
| AS-03 | Focus priority prevents shutter release without focus on the target bodies | R-01 tier 1 logic must be revised per brand | V-15 |
| AS-04 | A PTP path from Windows without driver replacement exists (WPD) | Tethering needs a driver step or a .NET helper | V-13 |

### 2.7 Out of scope

Buy or price advice; absolute shutter speed measurement (C5); internal camera service logs; Wi-Fi transport; mobile app; cloud services; repair guidance.

## 3. Functional requirements

### 3.1 Session management (SES)

| ID | Requirement | Pri | Release | Source |
| --- | --- | --- | --- | --- |
| FR-SES-01 | The system shall create a session folder containing a manifest, plan, frames, results and report. | M | v0.1 | H§5 p6 |
| FR-SES-02 | The system shall save session state after every completed step and shall resume an interrupted session at the first incomplete step. | M | v0.1 | new |
| FR-SES-03 | The system shall record the user-entered body serial (optional) and the serial read from the camera or metadata. | M | v0.1 | H§6 A1 |
| FR-SES-04 | The system shall store frames as copies; it shall never modify or delete files on the camera or the source card. | M | v0.1 | H§5 |
| FR-SES-05 | The system should allow opening a completed session read-only and re-rendering its report. | S | v0.1 | H§5 p6 |
| FR-SES-06 | The system may compare a session with an earlier session of the same body and report differences (new or removed defective pixels, dust changes, shutter count delta). | C | v0.5 | N-06 |

### 3.2 Camera identification and connection (CON)

| ID | Requirement | Pri | Release | Source |
| --- | --- | --- | --- | --- |
| FR-CON-01 | The system shall identify brand and model from the first imported frame's metadata when no camera is connected. | M | v0.1 | R-02 |
| FR-CON-02 | The system shall define a backend interface covering: device info, session open and close, storage listing, object transfer, property get and set, capture, and capability query. | M | v0.3 | H§5 |
| FR-CON-03 | The system shall detect a connected camera over USB and select a backend in the order: user-configured SDK adapter, PTP backend, file import. | M | v0.3 | H§6 step 0 |
| FR-CON-04 | The system shall display the required USB mode and conflicting settings for the detected brand (Sony Remote Shooting; Canon built-in Wi-Fi off) before connecting. | M | v0.3 | H§6 step 0 `[Sourced]` |
| FR-CON-05 | The system shall not require replacing the operating system's camera driver for the default Windows connection path; if a driver change is needed, the system shall explain it and how to revert it before proceeding. | M | v0.3 | R-03, V-13 |
| FR-CON-06 | The system shall load vendor SDK adapters as plugins from a user-supplied location and shall run without them. | S | v0.5 | R-11 |
| FR-CON-07 | The system shall fall back to file import, and record the reason, whenever a backend fails during a session. | M | v0.3 | H§5 p7 |

### 3.3 Acquisition and import (ACQ)

| ID | Requirement | Pri | Release | Source |
| --- | --- | --- | --- | --- |
| FR-ACQ-01 | The system shall import frames from a folder or a mounted card, copying them into the session. | M | v0.1 | H§5 |
| FR-ACQ-02 | The system shall ignore files whose capture time precedes the session start, unless the user explicitly includes them (protects previous-owner images). | M | v0.1 | CON-05 |
| FR-ACQ-03 | The system shall classify imported frames as dark, flat, chart, burst or other, and let the user confirm or correct the classification. | M | v0.1 | N-04 |
| FR-ACQ-04 | The system shall map classified frames to plan steps by capture settings and order. | M | v0.1 | N-04 |
| FR-ACQ-05 | In tethered mode the system shall apply the capture settings required by each step, capture, and download the RAW file. | M | v0.3 | H§6 |
| FR-ACQ-06 | The system shall record, before changing any camera setting, the original value, and shall offer to restore all changed settings at session end. | M | v0.3 | new |
| FR-ACQ-07 | The system shall count actuations caused by the session and show the running count against the plan. | M | v0.1 | H§5 p5 |
| FR-ACQ-08 | The system may record audio during burst steps and detect shutter onsets. | C | v0.5 | N-05 |

### 3.4 Frame acceptance and provenance (GATE)

| ID | Requirement | Pri | Release | Source |
| --- | --- | --- | --- | --- |
| FR-GATE-01 | The system shall evaluate every frame against the acceptance rules of its step before analysis: exposure settings, NR settings, histogram range, clipping, flicker banding, and (group D) selected AF point. | M | v0.1 | R-14 |
| FR-GATE-02 | The system shall keep rejected frames as evidence with the rejection reason and shall exclude them from analysis. | M | v0.1 | R-14 |
| FR-GATE-03 | The system shall prompt for a re-shoot when a step has fewer accepted frames than required, within the step's shot limit. | M | v0.1 | H§6 |
| FR-GATE-04 | The system shall check that all frames of a session come from the same body (serial in maker notes) and match the user-entered serial when provided. | M | v0.1 | N-02 |
| FR-GATE-05 | The system shall check capture times against the session or remote-pack window and against file-number order. | M | v0.1 | N-02 |
| FR-GATE-06 | The system shall flag frames whose metadata indicates editing software or missing maker notes. | S | v0.1 | N-02 |
| FR-GATE-07 | When provenance cannot be determined, the system shall lower the confidence of dependent results and state why. | M | v0.1 | N-02 |

### 3.5 Metadata and RAW decoding (META)

| ID | Requirement | Pri | Release | Source |
| --- | --- | --- | --- | --- |
| FR-META-01 | The system shall decode RAW frames to CFA arrays with black level, white level and CFA pattern. | M | v0.1 | R-08 |
| FR-META-02 | The system shall read metadata including maker notes and preserve the full metadata dump per frame in the session. | M | v0.1 | H§5 |
| FR-META-03 | When a RAW format cannot be decoded, the system shall explain the DNG conversion option and accept DNG input. | S | v0.1 | R-08, V-14 |
| FR-META-04 | The system shall accept JPEG input only for tests that declare JPEG support, with confidence capped at Low. | S | v0.1 | R-08 |
| FR-META-05 | The system shall record sensor or camera temperature when the metadata exposes it. | S | v0.2 | R-15 |

### 3.6 Tests (TST)

Detailed procedures, analysis and verdict rules are in [TEST-CATALOGUE.md](TEST-CATALOGUE.md). The requirements below apply to all tests.

| ID | Requirement | Pri | Release | Source |
| --- | --- | --- | --- | --- |
| FR-TST-01 | Each test shall declare: ID, group, supported paths, required frame types and counts, maximum shots, estimated minutes, prerequisites, and the KB fields it uses. | M | v0.1 | H§5 |
| FR-TST-02 | Each test shall produce a result with level, confidence, severity (when Suspect or Fail), path used, evidence references, and a plain-language explanation. | M | v0.1 | H§5 |
| FR-TST-03 | A test that did not run, or ran with insufficient accepted frames, shall be Not tested with a reason; it shall never be Pass. | M | v0.1 | H§5 p2 |
| FR-TST-04 | AF (group D) and metering (group E) tests shall not report Fail from a single lens or a single repetition; they report Suspect with confidence. | M | v0.2 | D-03, H§6 |
| FR-TST-05 | Tests shall prefer relative comparisons (within the session, versus the centre point, versus a reference speed) over absolute thresholds; every absolute threshold shall be a named, documented parameter labelled with its evidence status. | M | v0.1 | H§5 p4 |
| FR-TST-06 | AF tier 1 shall be determined from focus failure or shutter non-release (timeout or user report), not from in-focus metadata alone. | M | v0.2 | R-01, V-15 |
| FR-TST-07 | Manual (group F) items shall record the user's level, notes and optional photo, with path = manual. | M | v0.1 | H§6 F |

Test-to-release mapping:

| Release | Tests |
| --- | --- |
| v0.1 | A1, A3, A6 (metadata); B1, B2, B3, B4; C1 (EXIF timing); F reduced |
| v0.2 | A4 (KB), B5, B6, C2, C3, C4, D5 (file import), E1, E5, F full |
| v0.3 | Step 0 tethered; A1 to A5 via USB; tethered capture for B, C, E; D tier 1 by timeout |
| v0.4 | D1 to D4, D9, D10 (full AF map); E2, E3, E4, E6, E7 |
| v0.5 | D6, D7, D8 (SDK adapters); C1 with audio; C6 audio capture |

### 3.7 Verdict (VER)

| ID | Requirement | Pri | Release | Source |
| --- | --- | --- | --- | --- |
| FR-VER-01 | The system shall assign severity Blocker, High, Medium or Low to each Suspect or Fail result using rules defined per test. | M | v0.1 | H§9 |
| FR-VER-02 | The system shall not compute a single aggregate score. | M | v0.1 | H§9 |
| FR-VER-03 | On a Blocker during the first two plan phases (step 0, group A, reduced F), the system shall recommend stopping and let the user decide. | M | v0.1 | H§8 |
| FR-VER-04 | A known issue from the curated KB shall raise the priority of its confirming test and show a warning; it shall never by itself produce Suspect or Fail. | M | v0.2 | H§9 |
| FR-VER-05 | Results from remote-pack frames shall be capped at Medium confidence and labelled as seller-supplied. | M | v0.2 | N-01 |

### 3.8 Report (REP)

| ID | Requirement | Pri | Release | Source |
| --- | --- | --- | --- | --- |
| FR-REP-01 | The system shall write `report.json` conforming to a versioned schema as the canonical record. | M | v0.1 | R-09 |
| FR-REP-02 | The system shall render a single self-contained `report.html` from `report.json`, viewable offline and printable. | M | v0.1 | R-09, N-10 |
| FR-REP-03 | The report shall contain: summary counts per result level; Blockers first; camera info (brand, model, serial, firmware, shutter count before and after, lens); results per group with confidence and path; evidence images; Not tested list with reasons; suggested actions. | M | v0.1 | H§9 |
| FR-REP-04 | The report shall include an evidence manifest with SHA-256 of every source frame and evidence image, and show the manifest hash in the header. | M | v0.1 | R-09 |
| FR-REP-05 | The report shall not contain buy advice, price advice or an overall pass or fail of the camera. | M | v0.1 | H§9 |
| FR-REP-06 | The report shall state the app version, KB version, analysis parameter set and evidence labels of any threshold used. | M | v0.1 | H§0 |
| FR-REP-07 | The report shall show shutter count plausibility checks with their basis. | S | v0.2 | N-03 |

### 3.9 Knowledge base (KB)

| ID | Requirement | Pri | Release | Source |
| --- | --- | --- | --- | --- |
| FR-KB-01 | The system shall load curated KB entries from versioned YAML files validated against a schema. | M | v0.2 | H§9 |
| FR-KB-02 | Each curated entry and known issue shall carry a source and a confidence; entries without an official source shall have Low confidence. | M | v0.2 | H§9 |
| FR-KB-03 | The system shall build a derived model record from the session's own frames and store it in the session, separate from curated data. | M | v0.1 | R-07 |
| FR-KB-04 | A missing curated entry shall lower confidence or mark individual checks Not tested with reason "no reference data"; it shall not block a test. | M | v0.1 | R-07 |
| FR-KB-05 | If `metadata_decoder` is not `verified` for a model, metadata-based AF point confirmation shall be skipped for that model and stated in the report. | M | v0.4 | H§9 |
| FR-KB-06 | The repository shall provide a KB validation command usable in CI and by contributors. | M | v0.2 | H§9 |

### 3.10 Planning (PLN)

| ID | Requirement | Pri | Release | Source |
| --- | --- | --- | --- | --- |
| FR-PLN-01 | The system shall offer Quick, Standard and Full profiles as starting plans. | M | v0.1 | H§8 |
| FR-PLN-02 | The system shall show, before any shooting, planned shots, estimated minutes and, if rated life is known, actuations as a share of rated life. | M | v0.1 | H§8 |
| FR-PLN-03 | The user shall be able to deselect tests; deselected tests appear as Not tested with reason "skipped by user". | M | v0.1 | H§8 |
| FR-PLN-04 | The system should accept a shot budget and a time budget and propose a reduced plan, listing what was dropped. | S | v0.2 | R-10 |
| FR-PLN-05 | The plan shall order tests by increasing shooting cost: step 0 and A, reduced F, B, C, E, D. | M | v0.1 | H§8 |

### 3.11 Guidance and manual checks (GUI)

| ID | Requirement | Pri | Release | Source |
| --- | --- | --- | --- | --- |
| FR-GUI-01 | Every step shall show what to do, which camera settings to use, and what the user should see, with an illustration where useful. | M | v0.1 | H§1 |
| FR-GUI-02 | Steps that cannot be automated on the current path shall become guided manual steps, and the report shall record path = manual or semi-automatic. | M | v0.1 | H§5 p7 |
| FR-GUI-03 | The system shall export solid-colour images (red, green, blue, white, black) for LCD and EVF checks. | S | v0.2 | H§6 F |
| FR-GUI-04 | The system shall display the preparation equipment list relevant to the plan. | M | v0.1 | H§6 |
| FR-GUI-05 | The system shall provide a demo session generated from synthetic frames. | C | v0.1 | N-09 |

### 3.12 Field kit and remote pack (KIT)

| ID | Requirement | Pri | Release | Source |
| --- | --- | --- | --- | --- |
| FR-KIT-01 | The system shall export a printable field kit for a plan: shooting script with settings per step and group F checklist. | S | v0.2 | N-07 |
| FR-KIT-02 | The system shall generate a printable AF chart; per-model layout when the KB has it, generic grid otherwise. | S | v0.2 | H§6 D0 |
| FR-KIT-03 | The system shall export a remote pack: printable script plus a short plain-text version, including the time window and the request to send original unedited files. | S | v0.2 | N-01 |
| FR-KIT-04 | The system shall import a remote pack's returned files into a session marked as remote. | S | v0.2 | N-01 |

### 3.13 Settings (SET)

| ID | Requirement | Pri | Release | Source |
| --- | --- | --- | --- | --- |
| FR-SET-01 | The user shall be able to choose UI language (English, Vietnamese); the default follows the OS language, falling back to English. | M | v0.1 | D-15 |
| FR-SET-02 | The user shall be able to set the sessions folder, ExifTool path (if not bundled), and vendor SDK adapter paths. | M | v0.1 | H§13 |
| FR-SET-03 | The user shall be able to choose light or dark theme, defaulting to the OS setting. | C | v0.1 | UX |

## 4. External interface requirements

### 4.1 User interface

Specified in [UX.md](UX.md). Key requirements: wizard navigation with a persistent step list; result levels shown with colour, icon and text; keyboard operable; minimum 1280 x 720 `[Guess]` usable layout.

### 4.2 Hardware interfaces

- USB camera connection through PTP/MTP class drivers or user-supplied vendor SDK.
- Optional microphone (N-05).

### 4.3 Software interfaces

| Interface | Use | Notes |
| --- | --- | --- |
| LibRaw via rawpy | RAW decoding | Bundled; LGPL-2.1 replaceable (onedir) |
| ExifTool | Metadata and maker notes | Subprocess; bundling subject to V-16 |
| Vendor SDKs | Optional adapters | User-supplied; out of repo (R-11) |
| OS camera stack (WPD on Windows) | PTP transport | Subject to V-13 |

### 4.4 File formats

| Format | Direction | Notes |
| --- | --- | --- |
| CR2, CR3, NEF, ARW, DNG | In | As supported by bundled LibRaw (V-14) |
| JPEG | In | Limited tests, Low confidence |
| `session.json`, `plan.json`, `report.json` | In/Out | Versioned schemas |
| `report.html` | Out | Self-contained |
| PNG | Out | Evidence images, solid-colour test images, AF chart |
| KB YAML | In | Curated tier |

## 5. Non-functional requirements

| ID | Category | Requirement | Pri | Verification |
| --- | --- | --- | --- | --- |
| NFR-01 | Correctness | No test result shall be Pass unless the test ran on the required number of accepted frames. | M | Unit tests on verdict rules |
| NFR-02 | Correctness | On the synthetic defect suite, B1 to B4 shall detect at least 95% of injected defects with no more than 1 false defect per 10 megapixels `[Guess]`. Targets to be recalibrated on real cameras (V-07). | M | Automated test |
| NFR-03 | Performance | Analysis of one 24-megapixel RAW frame for B1 or B2 should complete within 5 s on a 4-core PC `[Guess]`. | S | Benchmark in CI |
| NFR-04 | Responsiveness | The GUI shall remain responsive during analysis and transfer (work runs off the UI thread) and show progress. | M | Manual and pytest-qt |
| NFR-05 | Reliability | Unplugging the camera or closing the app shall not lose completed steps (FR-SES-02). | M | Test |
| NFR-06 | Privacy | The app shall make no network requests by default. Any future update check shall be opt-in. | M | Inspection, network-off test |
| NFR-07 | Privacy | The app shall not read owner name, copyright, Wi-Fi or other personal settings from the camera; previous-owner images shall be excluded by default (FR-ACQ-02). | M | Inspection |
| NFR-08 | Transparency | Every threshold, parameter set and KB entry used shall be traceable from the report. | M | Inspection |
| NFR-09 | Portability | Windows build shall run from an unpacked folder without administrator rights. | M | Release test |
| NFR-10 | Portability | Platform-specific code shall be confined to backends and packaging. | M | Import contract in CI |
| NFR-11 | Maintainability | Analysis and verdict modules shall have at least 90% line coverage `[Guess]`. | S | CI coverage |
| NFR-12 | Maintainability | Layer dependency rules ([ARCHITECTURE.md](ARCHITECTURE.md) section 6) shall be enforced in CI. | M | CI |
| NFR-13 | Licensing | Releases shall ship LICENSE, NOTICE and third-party licence texts; no vendor SDK files. | M | Release checklist |
| NFR-14 | Localisation | All user-visible strings (GUI, messages, report, field kit, remote pack) shall be translatable; English and Vietnamese catalogues shall be 100% complete in every release. | M | Translation coverage check in CI |
| NFR-15 | Accessibility | Result levels shall never be conveyed by colour alone; text contrast should meet WCAG 2.1 AA. | M | Review |
| NFR-16 | Security | The app shall not execute code from session files or KB files; YAML shall be loaded in safe mode. | M | Inspection, test |
| NFR-17 | Size | Windows release archive should stay under 250 MB `[Guess]`. | C | CI artefact check |

## 6. Data requirements

### 6.1 Session folder

```
<sessions>/<yyyymmdd-hhmm>-<model>-<serial-suffix>/
  session.json        identity, settings snapshot, path decisions, versions
  plan.json           selected tests, budgets, ordering
  frames/             copied originals, never modified
  frames.json         per-frame metadata summary, classification, gate result, SHA-256
  metadata/           full metadata dump per frame
  evidence/           generated maps and charts (PNG)
  results.json        per-test results
  report.json         canonical report (schema-versioned)
  report.html         rendered report
```

### 6.2 Retention

Sessions are kept until the user deletes them. The app provides "delete session" and "export session as zip".

### 6.3 Schemas

Report and KB schemas are defined in [ARCHITECTURE.md](ARCHITECTURE.md) section 5 and versioned with SemVer; the report states its schema version.

## 7. Verification approach

| Method | Used for |
| --- | --- |
| Test (automated) | Analysis, verdict, gate, schemas, planner, report rendering |
| Demonstration | Wizard flows, tethered capture on real cameras (hardware test protocol in [ROADMAP.md](ROADMAP.md)) |
| Inspection | Privacy, licensing, traceability, accessibility |
| Analysis | Threshold calibration against real-camera data (V-07) |

Each release's acceptance criteria are listed in [ROADMAP.md](ROADMAP.md).

## 8. Traceability (summary)

| Requirement group | Handoff sections | Design review items | Tests (catalogue) |
| --- | --- | --- | --- |
| SES | H§5, H§9 | N-06 | All |
| CON | H§4, H§6 step 0, H§13 | R-03, R-11 | A1 to A5 |
| ACQ | H§5, H§6 | R-02, N-04, N-05 | B, C, D, E |
| GATE | H§6, H§11 | R-14, N-02 | All capture tests |
| META | H§5 | R-08, R-15 | A3, A6, B, D |
| TST | H§5, H§6 | R-01, R-04, R-05, R-06 | A to F |
| VER | H§9 | N-01 | All |
| REP | H§9 | R-09, N-03, N-10 | All |
| KB | H§9 | R-07 | A3, A4, D1, D9 |
| PLN | H§8 | R-10 | All |
| KIT | H§6 D0 | N-01, N-07 | D, F |
