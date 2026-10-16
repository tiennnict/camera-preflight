# Development Plan

Status: draft for maintainer review. Scope references point to [SRS.md](SRS.md) requirements and [TEST-CATALOGUE.md](TEST-CATALOGUE.md) tests. Effort sizes are `[Guess]` for a single part-time maintainer; no calendar dates are committed.

## 1. Approach

- **Value first, hardware last**: everything that works from files (analysis, wizard, report) ships before USB control (R-02). Each release is usable on its own.
- **Risk retired early**: spikes and verification tasks that can invalidate the design run in parallel with the first milestones (section 4).
- **Release from the start**: CI produces a Windows build from M0 so packaging and antivirus problems surface early (H§13).
- **Definition of Done** applies to every work item (section 6).

## 2. Release map

| Release | Milestone | Theme | User value |
| --- | --- | --- | --- |
| (internal) | M0 | Foundation | None for end users; repo, CI, schemas, synthetic data |
| 0.0.x pre-release | M1 | Analysis core and CLI | Technical users can analyse dark and flat frames from a folder |
| **v0.1** | M2 | Quick by file import, GUI wizard | On-site buyer can run Quick with a printed script and get a report |
| **v0.2** | M3 | Standard by file import, remote pack | Home and remote buyers get B, C, D5, E1, E5 and remote checks |
| **v0.3** | M4 | USB control, Canon first | Tethered capture, step 0 automation, tier 1 AF by timeout |
| **v0.4** | M5 | Full AF and knowledge base v1 | Full AF map, Full profile, curated KB for priority models |
| **v0.5** | M6 | Nikon and Sony, extras | More backends, SDK adapter interface, audio burst, compare |

## 3. Milestones

### M0 Foundation (size: M)

Scope:

- Repo setup: `pyproject.toml`, uv lock, ruff, pyright, pytest, import-linter, pre-commit.
- i18n foundation (D-15): gettext catalogues for `en` and `vi`, string extraction, CI check for untranslated strings.
- CI: lint, type, test on Windows and Linux; release workflow building a PyInstaller onedir zip with a `--self-test` smoke run.
- `domain` models; report, session and KB schemas (pydantic) with JSON Schema export.
- `synth` generator v1: CFA frames with noise, vignetting, and injected pixel defects and dust, with ground truth.
- NOTICE, CONTRIBUTING, CHANGELOG, `.gitignore` additions.

Exit criteria:

- CI green on both OS; tagged pre-release produces a downloadable Windows zip that runs `--self-test`.
- Schemas versioned and exported; synthetic generator reproducible from a seed.

### M1 Analysis core and CLI (size: L)

Scope: FR-META-01 to 04, FR-ACQ-01 to 04, FR-GATE-01 to 07, FR-TST-01 to 03, 05, FR-VER-01 to 02, FR-REP-01 to 06, FR-KB-03 to 04, FR-SES-01 to 04. Tests A1, A3, A6, B1 to B4, C1.

- `io`: rawpy decoding, ExifTool wrapper, importer, frame classification (N-04).
- `gate`: rules G1 to G7, provenance (N-02).
- `analysis`: robust per-channel statistics, defect detection, dust blobs with f/22 versus f/8 comparison, burst interval analysis.
- `checks`: A1, A3, A6, B1 to B4, C1 with parameter set `default-1` (all thresholds labelled).
- `report`: JSON, HTML, manifest.
- CLI: `camera-preflight analyse <folder> --profile quick`.

Exit criteria:

- Synthetic suite meets NFR-02 targets for B1 to B4.
- At least 3 real RAW samples per priority brand decode and produce a report (V-14 partially closed).
- Report for a synthetic session is stable under snapshot test.

### M2 Wizard GUI and v0.1 (size: L)

Scope: FR-GUI-01, 02, 04, 05, FR-PLN-01 to 03, 05, FR-SES-02, 05, FR-TST-07, FR-VER-03, FR-SET-01 to 03, NFR-04, 14, 15. Screens S0 to S10 for the file-import path (S2 without USB).

- `wizard` state machine with persistence and resume.
- `gui` shell, step runner, import and classify, manual check items, results, detail views, report export.
- Reduced F checklist; demo session (N-09); English and Vietnamese catalogues complete (D-15).
- Usability test round 1 (UX section 10).

Exit criteria:

- J1 completable end to end on the demo session and on at least one real camera's files.
- Usability round 1 success measures met or findings addressed.
- v0.1 Windows zip published with LICENSE, NOTICE, third-party licences (NFR-13), after V-11 is closed for shipped dependencies.

### M3 Standard by file import, remote pack, v0.2 (size: L)

Scope: tests A4, B5, B6, C2, C3, C4, D1 (derived), D3 to D5, D9, E1, E5, full F. FR-TST-04, 06 (user-reported path), FR-VER-04, 05, FR-REP-07, FR-KB-01, 02, 06, FR-PLN-04, FR-KIT-01 to 04, FR-GUI-03, FR-META-05.

- Budget planner (R-10); field kit and AF chart (N-07); remote pack and remote session mode (N-01); shutter count plausibility (N-03).
- Curated KB schema and validator; seed entries for a few priority models (O-02).
- Synthetic suite extended: curtain gradients, flicker, banding, AF blur per region.

Exit criteria:

- Synthetic suite covers every analysed test in the release.
- Remote pack dry run (UX round 2) completed.
- KB validator runs in CI.

### M4 USB control, Canon first, v0.3 (size: XL, highest technical risk)

Precondition: spike S-USB (section 4) has selected the transport.

Scope: FR-CON-02 to 05, 07, FR-ACQ-05 to 07, tethered paths for step 0, A1 to A5, B, C, E1, E5, D5; tier 1 AF by timeout (FR-TST-06).

- Backend host process and protocol (P-02); Canon PTP backend; property mapping; capture with timeout and focus-failure detection; settings restore.
- Hardware test protocol and log for each supported body.

Exit criteria:

- J3 Standard completed tethered on at least 2 Canon bodies of different generations, logged in `docs/hardware-log/`.
- Unplug test: no lost steps (NFR-05).
- No driver replacement on the default Windows path, or an approved alternative per FR-CON-05.

### M5 Full AF and knowledge base v1, v0.4 (size: L)

Scope: D2 to D4 on all points, D10, E2 to E4, E6, E7; FR-KB-05; curated KB v1 for the priority model list; AF layouts for those models.

Exit criteria:

- KB v1 entries all carry sources and confidence; at least one confirming test run per known issue where a body was available.
- Full profile run on at least one Canon body with two lenses.

### M6 Nikon and Sony, extras, v0.5 (size: XL)

Scope: Nikon and Sony backends (subject to V-04); SDK adapter plugin interface (FR-CON-06) with adapters outside the repo (R-11); D6 to D8 where adapters exist; N-05 audio burst; N-06 compare; macOS build exploration.

Exit criteria: defined at the start of M6 from verification results.

## 4. Parallel tracks: spikes and verification

Verification tasks are listed in [VERIFICATION.md](VERIFICATION.md). The plan schedules them against the milestone that needs the answer.

| Track | Tasks | Must be closed before |
| --- | --- | --- |
| S-RAW: RAW and metadata coverage | V-14, V-16, V-17, V-20 | End of M1 |
| S-LIC: Licences and NOTICE | V-11, V-16, V-19 | v0.1 release |
| S-AF: focus priority behaviour | V-15, V-06 | Start of M3 (D5), M5 (D2) |
| S-USB: transport spike on Windows | V-09, V-10, V-13, V-04, V-05 | Start of M4 (start the spike during M2) |
| S-SDK: vendor terms and access | V-01, V-02, V-03 | Start of M6 (start reading terms during M1, Canon application has a 2 to 4 week lead time `[Sourced]`) |
| S-CAL: threshold calibration | V-07 | v0.2 for B and C; v0.4 for D and E |
| S-SIGN: code signing | V-12, O-03 | v0.1 if decided; otherwise unsigned with documented SmartScreen steps |

Spike S-USB outline:

1. WPD: enumerate a Canon body, open a session, `GetDeviceInfo`, read property 0xD1AC, capture, download.
2. Repeat with libusb plus WinUSB on a test machine; note driver install and revert steps.
3. If both fail on Canon: .NET helper around FC.SDK using the same JSON protocol.
4. Output: a short decision record with measured results; update [DECISIONS.md](DECISIONS.md).

## 5. Work breakdown (epics)

| Epic | Milestones | Main packages |
| --- | --- | --- |
| E1 Foundation and CI | M0 | repo, packaging, `.github` |
| E2 Domain and schemas | M0 | `domain`, `report` schema, `knowledge` schema |
| E3 Synthetic data | M0, M1, M3 | `synth` |
| E4 Import, decode, classify | M1 | `io` |
| E5 Gate and provenance | M1 | `gate` |
| E6 Sensor analysis | M1, M3 | `analysis.pixels`, `analysis.dust`, `analysis.uniformity` |
| E7 Shutter analysis | M1, M3 | `analysis.shutter` |
| E8 AF analysis | M3, M5 | `analysis.af`, `kit` chart |
| E9 Metering analysis | M3, M5 | `analysis.metering` |
| E10 Checks and verdict | M1 to M5 | `checks` |
| E11 Report | M1, M3 | `report` |
| E12 Wizard and GUI | M2 to M5 | `wizard`, `gui` |
| E13 Planning and kits | M2, M3 | `planning`, `kit` |
| E14 Knowledge base content | M3, M5 | `knowledge-base/` |
| E15 Backends | M4, M6 | `backends`, `acquisition` |
| E16 Localisation and accessibility | M2 onward | `locale`, `gui` |

## 6. Definition of Done

A work item is done when:

1. Code passes ruff, pyright and import-linter.
2. Unit tests cover the change; analysis changes include synthetic-suite cases.
3. User-visible strings are translatable and translated in both catalogues, English and Vietnamese, in the same change (D-15); CI fails on a missing translation.
4. Any threshold added is a named parameter with an evidence label and appears in the report's Method data.
5. Docs updated: SRS traceability if a requirement changed; TEST-CATALOGUE if a test changed.
6. CI build succeeds and `--self-test` passes on the Windows artefact.

## 7. Ways of working

- Branches: `main` protected; work on feature branches; pull requests with CI required.
- Commits: Conventional Commits; CHANGELOG generated per release.
- Versioning: SemVer for the app; schema versions independent (ARCHITECTURE section 7).
- Issues: open verification tasks stay in [VERIFICATION.md](VERIFICATION.md) until the maintainer decides to open them as issues (maintainer decision, 2026-10-16).
- Hardware results: one Markdown log per body and session in `docs/hardware-log/`, with app version, firmware, steps, and outcome.

## 8. Risks to the plan

| Risk | Effect | Mitigation |
| --- | --- | --- |
| No reliable Windows PTP path (S-USB fails) | M4 slips or needs .NET helper | v0.1 and v0.2 do not depend on USB; helper protocol designed in P-02 |
| LibRaw lacks support for recent bodies | B tests unavailable for those models | DNG fallback (FR-META-03); state per model in KB |
| Thresholds wrong on real cameras | False Suspect or missed defects | Labelled parameters; calibration track S-CAL; Suspect before Fail |
| Antivirus flags builds | Users cannot run the app | onedir build; Nuitka fallback; consider signing (O-03) |
| Single maintainer capacity | Milestones stretch | Each release stands alone; scope can stop after v0.2 with a useful product |
| Vendor SDK terms forbid public adapters | D6 to D8 unavailable publicly | Adapters outside repo (R-11); tests remain Not tested with reason |
