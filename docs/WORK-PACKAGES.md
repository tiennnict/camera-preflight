# Work Packages

Status: draft, 2026-10-17. All Proposed blockers were resolved by D-46. Derived from the design baseline ([SRS.md](SRS.md), [TEST-CATALOGUE.md](TEST-CATALOGUE.md), [ARCHITECTURE.md](ARCHITECTURE.md), [UX.md](UX.md), [ROADMAP.md](ROADMAP.md)). The milestone order follows the release map, which is itself Proposed (P-07). Read [AGENTS.md](../AGENTS.md) before taking a package.

## 1. How to use this list

- Take a package only when every package in **Depends on** is merged and **Blocked by** is empty or approved. Check the current status of each blocker in [DECISIONS.md](DECISIONS.md).
- **Blocked by** lists Proposed decisions. A Proposed item is not binding (D-17): do not start the package, and do not implement an alternative instead.
- **Verification** lists open tasks in [VERIFICATION.md](VERIFICATION.md) that the package depends on or must help close. A package may start while they are open, but must record what it found and must not present an unverified fact as verified.
- **Requirements** are the acceptance criteria: each listed requirement has a test or an inspection note in the pull request. The Definition of Done ([ROADMAP.md](ROADMAP.md) section 6) applies to every package.
- One branch and one pull request per package: `wp/<id>-<short-name>`, for example `wp/wp-10-raw-decoding`.
- If a package is too large for one pull request, split it into `WP-xx.1`, `WP-xx.2` and say so in the pull request.

## 2. M0 Foundation (internal)

| ID | Work package | Deliverables | Requirements | Inputs | Depends on | Blocked by | Verification |
| --- | --- | --- | --- | --- | --- | --- | --- |
| WP-00 | Repository skeleton and tooling | `pyproject.toml`, `uv.lock`, ruff, pyright, pytest, hypothesis, import-linter contracts from ARCHITECTURE §6, pre-commit, NOTICE, CONTRIBUTING, CHANGELOG, empty package tree from ARCHITECTURE §6 | NFR-10, NFR-12 | ARCHITECTURE §2.4, §6 | - | P-03, R-12 | - |
| WP-01 | CI workflow | `.github/workflows/ci.yml`: lint, type check, import contracts, tests on Windows and Linux runners | NFR-12 | ARCHITECTURE §2.4, §8 | WP-00 | P-03 | - |
| WP-02 | Release workflow and packaging | `release.yml` on tag; PyInstaller onedir spec; zip with checksums; `--self-test` entry point; pinned ExifTool fetched at build time into the bundle | NFR-09, NFR-13, NFR-17 | ARCHITECTURE §2.4, LICENSING §3 | WP-00 | P-06 | V-16 |
| WP-03 | Internationalisation foundation | gettext domain, `locale/en` and `locale/vi` catalogues, extraction command, CI check that fails on an untranslated or missing string, language selection (OS default, else English) | CON-07, NFR-14, FR-SET-01 | UX §9, §10 | WP-00 | P-04 | - |
| WP-04 | Domain models and schemas | `domain`: Level, Confidence, Severity, ExecPath, AutomationLevel, Frame, CheckResult, Session, Message (code plus parameters); JSON Schema export for session and result data | FR-TST-01, FR-TST-02, SRS §6 | ARCHITECTURE §4, §5.1 | WP-00 | P-05, R-12 | - |
| WP-05 | Synthetic frame generator v1 | `synth`: CFA frames with shot and read noise, vignetting, hot, stuck and dead pixels, clusters, dust blobs scaled by aperture, scratches, banding; ground-truth JSON | NFR-02 | ARCHITECTURE §8, TEST-CATALOGUE §4 | WP-04 | R-08 | - |

## 3. M1 Analysis core and CLI (0.0.x pre-release)

| ID | Work package | Deliverables | Requirements | Inputs | Depends on | Blocked by | Verification |
| --- | --- | --- | --- | --- | --- | --- | --- |
| WP-10 | RAW decoding | `io/raw.py`: CFA array, CFA pattern, black and white levels via rawpy; DNG accepted; clear error for unsupported formats | FR-META-01, FR-META-03, FR-META-04 | SRS §3.5, §4.4 | WP-04 | R-08, P-05 | V-14 |
| WP-11 | Metadata reader | `io/metadata.py` interface and versioned field allowlist; `io/exiftool.py` using the bundled ExifTool in `-stay_open` mode; personal fields never stored or logged. If V-16 rules out bundling: in-house reader for the allowlisted fields (D-42) | FR-META-02, NFR-07, AS-02 | ARCHITECTURE §2.2, LICENSING §5 | WP-04 | - | V-16, V-17, V-20 |
| WP-12 | Session folder and per-step upload | Session folder layout from SRS §6.1, atomic writes, copies of originals, per-step file selection (never other files from a card) | FR-SES-01, FR-SES-03, FR-SES-04, FR-SES-08, FR-ACQ-01, FR-ACQ-02 | SRS §3.1, §6 | WP-04 | - | - |
| WP-13 | Acceptance gate and provenance | `gate`: rules G1 to G7 with plain rejection reasons (value found, value needed); same-body and serial checks; editing-software flags; confidence lowering | FR-GATE-01 to 04, 06, 07 | TEST-CATALOGUE §1 | WP-10, WP-11 | R-14, N-02 | - |
| WP-14 | Pixel analysis B1, B2, B3, B6 | `analysis/pixels`: robust per-ISO statistics, hot, stuck and dead classification, clusters, banding; temperature recorded when available | FR-TST-05, NFR-02, NFR-03 | TEST-CATALOGUE §4 | WP-05, WP-10 | R-08, R-15 | V-07 |
| WP-15 | Dust and uniformity B4, B5 | `analysis/dust`, `analysis/uniformity`: blob detection, f/22 versus f/8 comparison, heat maps | NFR-02 | TEST-CATALOGUE §4 | WP-05, WP-10 | R-06, R-13 | V-07 |
| WP-16 | Shutter analysis C1 to C4 | `analysis/shutter`: burst intervals from timestamps, curtain profiles against a slow reference, repeatability, mechanical versus electronic | FR-TST-05 | TEST-CATALOGUE §5 | WP-05, WP-10, WP-11 | R-05 | V-17, V-07 |
| WP-17 | Metering analysis E1, E2, E4 to E7 | `analysis/metering`: exposure spread, mode comparison, linearity of compensation, ISO and aperture steps | FR-TST-04, FR-TST-05 | TEST-CATALOGUE §7 | WP-05, WP-10, WP-11 | - | V-07 |
| WP-18 | Check framework and verdict rules | `checks`: check declarations (automation level per mode, frames, gate rules, SDK needs, KB fields), parameter set `default-1` with evidence labels, severity rules, Not tested reasons | FR-TST-01 to 05, FR-VER-01, FR-VER-02, NFR-01, NFR-08 | TEST-CATALOGUE, SRS §3.6, §3.7 | WP-13, WP-14, WP-15, WP-16, WP-17 | - | - |
| WP-19 | Derived knowledge tier | `knowledge`: derived model record from the session's own frames; resolver (curated, else derived with lower confidence, else no reference data) | FR-KB-03, FR-KB-04 | ARCHITECTURE §5.2 | WP-11 | R-07 | - |
| WP-20 | HTML report | `report`: one self-contained HTML file in the chosen language; camera info with shutter count before and after; results with confidence and path; evidence images; Not tested list; method data. The SHA-256 manifest part waits for N-10 | FR-REP-02 to 06, 09, FR-SES-07, D-37 (FR-REP-04 only after N-10) | SRS §3.8 | WP-18, WP-03 | N-10 (manifest part only) | - |
| WP-21 | Command-line interface | `camera-preflight analyse --check <id> <files>` producing results and the report | - | ROADMAP M1 | WP-18, WP-20 | - | - |

## 4. M2 Full wizard in upload mode (v0.1)

| ID | Work package | Deliverables | Requirements | Inputs | Depends on | Blocked by | Verification |
| --- | --- | --- | --- | --- | --- | --- | --- |
| WP-30 | Wizard engine | `wizard`: phases in order (start, blocker, automatic, semi-automatic, manual, results), check ordering by automation level, skip, auto-advance hooks, no resume, no history | FR-TST-08, 09, 11, FR-SES-08 | UX §3, TEST-CATALOGUE §9 | WP-18 | - | - |
| WP-31 | GUI shell | Top bar, step list with live status, bottom bar, home (S1), settings (S13 without SDK part), theme, reduced motion, keyboard operation | FR-SET-01 to 03, FR-GUI-08, FR-GUI-09, NFR-04, NFR-15 | UX §4, §5, §8 to §10, §12 | WP-30, WP-03 | P-01 | - |
| WP-32 | Upload steps | Screen S8 for every shooting step: parameter table, upload button, per-file validation with reasons, model identified from the first file | FR-ACQ-01, FR-GATE-02, FR-GATE-03, FR-CON-09, FR-GUI-01 | UX §3.4, §9 | WP-31, WP-12, WP-13 | P-01 | - |
| WP-33 | Animation engine and scenes | Layered SVG plus timeline player on QGraphicsView; 24 scenes from UX §6; static key frame under reduced motion; control labels from gettext | FR-GUI-06 | UX §6, D-18 to D-21 | WP-31 | - | - |
| WP-34 | Reference photos | `gui/reference/` with up to 4 photos per defect and ATTRIBUTION.md; credit shown under each photo and in About | FR-GUI-07, NFR-13, CON-08 | UX §7, REFERENCE-IMAGES | WP-31 | - | V-24 |
| WP-35 | Blocker and manual checks | Screens S3 and S9: questions and checklists for group F, level buttons, notes, photo attachment, solid-colour images | FR-TST-07, FR-TST-11, FR-GUI-03 | UX §5, TEST-CATALOGUE §8 | WP-33, WP-34 | - | - |
| WP-36 | AF from uploaded files | `analysis/af` and checks D1 to D5, D9, D10, E3 from uploads; AF chart file in `guide`; tier 1 reported by the user | FR-TST-04, FR-TST-06 | TEST-CATALOGUE §6 | WP-18, WP-32 | R-01 | V-06, V-15 |
| WP-37 | Results, detail and report screens | Screens S10, S11, S12 | FR-REP-03, NFR-15 | UX §5 | WP-20, WP-31 | - | - |
| WP-38 | Demo session | Synthetic session used by the GUI, the usability test and `--self-test` | FR-GUI-05 | ROADMAP M2 | WP-05, WP-30 | N-09 | - |
| WP-39 | Release compliance | NOTICE, third-party licence texts, photo attributions in the release; README steps for the SmartScreen prompt | NFR-13, D-41 | LICENSING | WP-02, WP-34 | - | V-11, V-16, V-19, V-24 |
| WP-3A | Usability round 1 | Moderated test, findings in `docs/ux-findings/` | - | UX §11 | WP-32, WP-35, WP-37, WP-38 | N-09 | - |

## 5. M3 Connected mode, Canon and Sony (v0.2)

| ID | Work package | Deliverables | Requirements | Inputs | Depends on | Blocked by | Verification |
| --- | --- | --- | --- | --- | --- | --- | --- |
| WP-40 | Spike: USB transport on Windows | Measured results for WPD, then libusb, then a .NET helper, on one Canon and one Sony body; decision record | FR-CON-05 | ROADMAP §4 | - | R-03 | V-09, V-10, V-13 |
| WP-41 | Backend host and protocol | Separate backend host process, JSON messages over stdio, client in the app, crash isolation | FR-CON-02, NFR-05 | ARCHITECTURE §2.3, §4 | WP-04 | P-02 | - |
| WP-42 | PTP core | Shared PTP layer on the chosen transport: session, device info, storage, objects, properties, capture, live view | FR-CON-02 | ARCHITECTURE §2.3 | WP-40, WP-41 | - | - |
| WP-43 | Canon PTP backend | Canon operations including shutter count where readable | FR-CON-03, FR-ACQ-05 | TEST-CATALOGUE §3 | WP-42 | - | V-05 |
| WP-44 | Sony PTP backend | Sony operations for identification, settings, capture and download | FR-CON-03, FR-ACQ-05 | TEST-CATALOGUE §3 | WP-42 | - | V-04 |
| WP-45 | SDK framework and first-run setup | Adapter loading inside the backend host, default and custom folders, screen S0 and the SDK part of S13, Not tested reason "SDK not configured", SDK test environment | FR-CON-06, FR-CON-07 | UX §5, LICENSING §2 | WP-41, WP-31 | - | V-01, V-23 |
| WP-46 | Canon SDK adapter | `backends/sdk/canon` | FR-CON-03 | LICENSING §2 | WP-45 | - | V-01, V-02, V-23 |
| WP-47 | Sony SDK adapter | `backends/sdk/sony` | FR-CON-03 | LICENSING §2 | WP-45 | - | V-01, V-02, V-23 |
| WP-48 | Detection and connection states | Continuous camera and driver detection, USB mode hints, screens S2 and S14, reconnect or switch to upload | FR-CON-01, 04, 05, 08, NFR-05 | UX §2, §5 | WP-42, WP-31 | - | - |
| WP-49 | Automatic phase | Screen S4: A1 to A5, settings applied with originals recorded and restored, C1, retry then manual fallback, auto-advance | FR-ACQ-05, 06, 09, FR-TST-10, NFR-18 | UX §3.2, TEST-CATALOGUE §9 | WP-43, WP-44, WP-30 | - | - |
| WP-4A | Helpers H1, H2, H5, H7 | Detectors with button fallback after a time limit; grouped runs after one trigger; tests on recorded live view | FR-ACQ-10 to 12 | UX §3.3 | WP-49 | - | V-22 |
| WP-4B | Shutter count plausibility and temperature | Plausibility checks in the report; sensor temperature recorded when exposed | FR-REP-07, FR-META-05 | SRS §3.5, §3.8 | WP-43, WP-44, WP-20 | N-03, R-15 | V-20 |
| WP-4C | Hardware test protocol | Protocol and one log per body in `docs/hardware-log/`; usability session on a real body | - | ROADMAP M3, UX §11 | WP-49, WP-4A | - | - |

## 6. M4 Connected AF and knowledge base v1 (v0.3)

| ID | Work package | Deliverables | Requirements | Inputs | Depends on | Blocked by | Verification |
| --- | --- | --- | --- | --- | --- | --- | --- |
| WP-50 | Helpers H3, H4, H6 | Chart in view, steady camera, focus mode | FR-ACQ-10, 11 | UX §3.3 | WP-4A | - | V-22 |
| WP-51 | Connected AF run | AF point selection and focus drive by the app where the backend allows, button per point otherwise; D1 to D5, D10, E3 connected | FR-TST-06, FR-ACQ-05 | TEST-CATALOGUE §6, §9 | WP-36, WP-50 | R-01 | V-03, V-06, V-15 |
| WP-52 | Sony D6 to D8 | Region sharpness map, AF response time, focus position on Sony | D-04 | TEST-CATALOGUE §6 | WP-47, WP-51 | - | - |
| WP-53 | Curated knowledge base tooling | YAML schema, loader, validation command for CI and contributors, known-issue handling | FR-KB-01, 02, 05, 06, FR-VER-04 | ARCHITECTURE §5.2 | WP-19 | R-07 | - |
| WP-54 | Knowledge base content v1 | Curated entries for every Canon, Nikon and Sony model with sourced data; one work package per brand is allowed | FR-KB-02, D-40 | ARCHITECTURE §5.2 | WP-53 | R-07 | - |

## 7. M5 Nikon (v0.4)

| ID | Work package | Deliverables | Requirements | Inputs | Depends on | Blocked by | Verification |
| --- | --- | --- | --- | --- | --- | --- | --- |
| WP-60 | Nikon PTP backend | Nikon operations | FR-CON-03, FR-ACQ-05 | TEST-CATALOGUE §3 | WP-42 | - | V-04 |
| WP-61 | Nikon SDK adapter | `backends/sdk/nikon` | FR-CON-03 | LICENSING §2 | WP-45 | - | V-01, V-02, V-23 |
| WP-62 | Nikon D6 to D8 | Where the Nikon SDK allows | - | TEST-CATALOGUE §6 | WP-61, WP-51 | - | V-03 |

## 8. Blockers by Proposed decision

Approving an item unblocks the packages listed. Items with no package affect scope or later work only.

| Proposed item | Packages blocked |
| --- | --- |
| R-01 | WP-36, WP-51 |
| R-03 | WP-40 |
| R-05 | WP-16 |
| R-06 | WP-15 |
| R-07 | WP-19, WP-53, WP-54 |
| R-08 | WP-05, WP-10, WP-14 |
| R-12 | WP-00, WP-04 |
| R-13 | WP-15 |
| R-14 | WP-13 |
| R-15 | WP-14, WP-4B |
| N-02 | WP-13 |
| N-03 | WP-4B |
| N-05 | none |
| N-06 | none (rejected by D-46) |
| N-09 | WP-38, WP-3A |
| N-10 | WP-20 |
| P-01 | WP-31, WP-32 |
| P-02 | WP-41 |
| P-03 | WP-00, WP-01 |
| P-04 | WP-03 |
| P-05 | WP-04, WP-10 |
| P-06 | WP-02 |
| P-07 | all (milestone order) |

## 9. Requirements not assigned to a package

| Requirement | Reason |
| --- | --- |
| FR-ACQ-08 | Audio burst rhythm (N-05), release "later" |

## 10. Status after the first implementation pass

Status of each package on `main`. "Done" means built, tested without a camera and merged. Nothing here has run on a real camera.

| Package | Status | Note |
| --- | --- | --- |
| WP-00 to WP-05 | Done | Skeleton, CI, i18n check, domain, synthetic generator and DNG writer |
| WP-10 to WP-12 | Done | RAW via rawpy, ExifTool and in-house readers, session folder, per-step upload |
| WP-13 to WP-19 | Done | Gate, analysis, checks A to F, verdict rules, derived knowledge tier. Thresholds are `[Guess]` until V-07 |
| WP-20, WP-21 | Done | HTML report with hashes (N-10), command line |
| WP-30 to WP-33, WP-35, WP-37, WP-38 | Done | Wizard engine, Qt shell, upload, manual, results, 24 scenes, demo session |
| WP-34 | Partial | Mechanism, credits and About screen done. No photo is included: the photo hosts were not reachable (V-24) |
| WP-36 | Done | AF from uploads; tier 1 reported by the user |
| WP-39 | Partial | NOTICE, licence collection and SmartScreen steps done; pinned ExifTool and photo credits still open (V-16, V-24) |
| WP-3A | Open | Needs five people (UX section 11) |
| WP-40 | Blocked | Needs hardware: Canon and Sony bodies on Windows |
| WP-41, WP-42, WP-45, WP-48 | Done | Host process, JSON protocol, PTP core, SDK loader and first-run setup, detection, lost-connection screen |
| WP-43, WP-44, WP-60 | Partial | Standard PTP operations only. Brand extras (Canon shutter count property, live view, remote AF point) are `[Unverified]` and stay off until hardware logs exist |
| WP-47, WP-61 | Bound, not run on a camera | `backends/sdk/sony.py` (Camera Remote SDK v2.02.00), `backends/sdk/nikon.py` (Remote SDK v2.1.0, Control Service Layer, Z bodies only) and `backends/sdk/nikon_module.py` (MAID3 `Type00xx.md3` modules for D-SLR bodies; built and load-tested against `Type0017.md3`, the D7200 module) are written from the vendor headers and samples and tested against fake layers. Layouts worked out by hand are `[Inference]`; camera behaviour is `[Unverified]` until a hardware log exists (V-23). Not bound: AF point selection, focus drive, Sony burst |
| WP-46 | Bound, not run on a camera | `backends/sdk/canon.py` is written from the EDSDK 2.13 headers, API reference and `CameraControl` sample, cross-checked against two open-source wrappers, and tested against a fake layer; the 64-bit library from that release loads and enumerates zero cameras. Camera behaviour is `[Unverified]` until a hardware log exists (V-23). Not bound: shutter count (not an EDSDK property; the PTP backend reads it), shutter mode, AF point, focus drive, focus mode (read only in the API), burst |
| WP-49, WP-4A, WP-50 | Done | Automatic run, helpers H1 to H5 and H7 with button fallback; H6 always uses the button (V-22) |
| WP-4B | Partial | Plausibility notes and temperature done; relies on shutter count being readable |
| WP-4C | Open | Protocol in [hardware-log/README.md](hardware-log/README.md); needs bodies |
| WP-51, WP-52, WP-62 | Partial | Connected AF runs by point when the backend can select a point, otherwise falls back by hand. D6 to D8 analysis exists; their data comes from SDK bindings that are not bound yet |
| WP-53 | Done | Schema, loader, validator, template |
| WP-54 | Partial | 17 entries with sourced known issues (Nikon, Canon and Sony service notices, plus labelled owner reports for the D7200 family); serial ranges, serial digit rules and firmware ranges are matched against the unit (D-50). Every other model still needs sourced data |
