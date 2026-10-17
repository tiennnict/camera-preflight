# Development Plan

Status: revised 2026-10-17 after maintainer decisions D-23 to D-38. Scope references point to [SRS.md](SRS.md) and [TEST-CATALOGUE.md](TEST-CATALOGUE.md). Effort sizes are `[Guess]` for a single part-time maintainer; no calendar dates are committed.

## 1. Approach

- **Upload mode first, connected mode next**: the full wizard works from uploaded files before USB control ships; both modes share the same checks and analysis. Each release is usable on its own.
- **Automation is the product**: once connected mode exists, every camera action possible over USB is done by the app (D-25, D-34). NFR-18 is reviewed for every check.
- **Risk retired early**: spikes and verification tasks run in parallel with the first milestones (section 4).
- **Release from the start**: CI produces a Windows build from M0 (H§13).
- **Definition of Done** applies to every work item (section 6).

## 2. Release map

| Release | Milestone | Theme | User value |
| --- | --- | --- | --- |
| (internal) | M0 | Foundation | Repo, CI, schemas, synthetic data |
| 0.0.x pre-release | M1 | Analysis core and CLI | Technical users can analyse dark and flat frames |
| **v0.1** | M2 | Full wizard in upload mode | Every check that works from files, blocker check, manual checks with reference photos, HTML report, English and Vietnamese |
| **v0.2** | M3 | Connected mode, Canon first | Detection, SDK first-run setup, automatic phase, helpers H1, H2, H5, H7, app-driven settings and capture, Canon PTP and Canon SDK adapter |
| **v0.3** | M4 | Connected AF and knowledge base v1 | Helpers H3, H4, H6; automatic AF runs on all points where the backend allows; curated KB for priority models |
| **v0.4** | M5 | Nikon and Sony | PTP backends and SDK adapters for Nikon and Sony; D6 to D8 where SDKs allow |
| later | | macOS and Linux, audio burst (N-05) | |

## 3. Milestones

### M0 Foundation (size: M)

- Repo setup: `pyproject.toml`, uv lock, ruff, pyright, pytest, import-linter, pre-commit.
- i18n foundation (D-15): gettext catalogues `en` and `vi`, string extraction, CI check for untranslated strings.
- CI: lint, type, test on Windows and Linux; release workflow building a PyInstaller onedir zip with a `--self-test` smoke run.
- `domain` models; result, session and KB schemas with JSON Schema export.
- `synth` generator v1: CFA frames with noise, vignetting, injected pixel defects and dust, with ground truth.
- NOTICE, CONTRIBUTING, CHANGELOG.

Exit: CI green on both OS; tagged pre-release produces a Windows zip that runs `--self-test`.

### M1 Analysis core and CLI (size: L)

Scope: FR-META-01 to 04, FR-GATE-01 to 04, 06, 07, FR-TST-01 to 05, FR-VER-01 to 02, FR-REP-02 to 06, 09, FR-KB-03 to 04. Checks A1, A3, A4, A6, B1 to B6, C1 to C4, E1, E2, E4 to E7 from files.

- `io`: rawpy decoding, ExifTool wrapper, per-step upload.
- `gate`: rules G1 to G7 with plain rejection reasons (D-30), provenance.
- `analysis`: pixels, dust, uniformity, shutter, metering.
- `checks` with parameter set `default-1` (every threshold labelled).
- `report`: HTML and manifest.
- CLI: `camera-preflight analyse --check B1 <files>`.

Exit: synthetic suite meets NFR-02 for B1 to B4; at least 3 real RAW samples per priority brand decode (V-14 partly closed); report snapshot test stable.

### M2 Full wizard in upload mode, v0.1 (size: L)

Scope: FR-TST-06 to 09, 11, FR-ACQ-01, 02, FR-GATE-03, FR-GUI-01, 03, 05 to 08, FR-SES-01, 03, 04, 07, 08, FR-SET-01 to 03, FR-CON-09, NFR-04, 14, 15. Checks D1 to D5, D9, D10, E3 in upload mode; group F manual checks.

- `wizard`: phases and ordering by automation level (D-34), skip, blocker check (D-35).
- `gui`: shell, upload steps with parameters and validation, manual checks with animations and reference photos, results, details, report.
- Animation library (24 scenes, D-19) and reference photos with attribution (D-38).
- Demo session (N-09).
- Usability test round 1 ([UX.md](UX.md) section 11).

Exit: upload mode end to end on the demo session and on real files of at least one body; usability round 1 met or findings fixed; v0.1 zip published with licences and photo attributions (NFR-13), after V-11 is closed for shipped dependencies.

### M3 Connected mode, Canon first, v0.2 (size: XL, highest technical risk)

Precondition: spike S-USB (section 4) has selected the transport.

Scope: FR-CON-01 to 08, FR-ACQ-05, 06, 09 to 12, FR-TST-10, FR-META-05, FR-REP-07, NFR-05, 18.

- Backend host process and protocol (P-02); Canon PTP backend; Canon SDK adapter tested in the SDK test environment (D-31, V-23).
- Camera and driver detection; first-run SDK setup screen (D-24).
- Automatic phase: A1 to A5, settings applied by the app, C1; auto-advance.
- Helpers H1 (dark sensor), H2 (flat field), H5 (lens changed), H7 (card) with button fallback.
- Fallback to guided manual steps when a command fails (D-25).
- Hardware test protocol and log per body.

Exit: connected mode end to end on at least 2 Canon bodies of different generations, logged in `docs/hardware-log/`; no step asks the user for something the backend can do (NFR-18); unplug test passes (NFR-05).

### M4 Connected AF and knowledge base v1, v0.3 (size: L)

Scope: FR-KB-01, 02, 05, 06, FR-VER-04; helpers H3 (chart), H4 (steady), H6 (focus mode); automatic AF runs (point selection and focus drive by the app where the backend allows, button per point otherwise); E3 connected.

Exit: AF run on at least one Canon body with two lenses; KB v1 entries all sourced.

### M5 Nikon and Sony, v0.4 (size: XL)

Scope: Nikon and Sony PTP backends (V-04) and SDK adapters; D6 to D8 where SDKs allow.

Exit: defined at the start of M5 from verification results.

## 4. Parallel tracks: spikes and verification

Verification tasks: [VERIFICATION.md](VERIFICATION.md).

| Track | Tasks | Must be closed before |
| --- | --- | --- |
| S-RAW: RAW and metadata coverage | V-14, V-16, V-17, V-20 | End of M1 |
| S-LIC: licences, NOTICE, photo attributions | V-11, V-16, V-19, V-24 | v0.1 |
| S-AF: focus priority behaviour | V-15, V-06, V-03 | Start of M4 |
| S-USB: transport spike on Windows | V-09, V-10, V-13, V-04, V-05 | Start of M3 (run the spike during M2) |
| S-SDK: SDK terms, access and test environment | V-01, V-02, V-23 | Start of M3 (Canon); M5 (Nikon, Sony). Canon application has a 2 to 4 week lead time `[Sourced]` |
| S-HLP: helper feasibility | V-22 | Start of M3 |
| S-CAL: threshold calibration | V-07 | v0.1 for B and C; v0.3 for D and E |
| S-SIGN: code signing | V-12, O-03 | v0.1 if decided |

Spike S-USB outline:

1. WPD: enumerate a Canon body, open a session, `GetDeviceInfo`, read property 0xD1AC, read live view, capture, download.
2. Repeat with libusb plus WinUSB; note driver install and revert steps.
3. If both fail: .NET helper around FC.SDK with the same JSON protocol.
4. Output: a decision record with measured results in [DECISIONS.md](DECISIONS.md).

## 5. Work breakdown (epics)

| Epic | Milestones | Main packages |
| --- | --- | --- |
| E1 Foundation and CI | M0 | repo, packaging, `.github` |
| E2 Domain and schemas | M0 | `domain`, schemas |
| E3 Synthetic data | M0, M1 | `synth` |
| E4 Decode and upload | M1 | `io` |
| E5 Gate and provenance | M1 | `gate` |
| E6 Sensor, shutter, metering analysis | M1 | `analysis` |
| E7 AF analysis | M2, M4 | `analysis.af`, `guide` chart |
| E8 Checks and verdict | M1 to M4 | `checks` |
| E9 Report | M1, M2 | `report` |
| E10 Wizard and GUI | M2 to M4 | `wizard`, `gui` |
| E11 Animations and reference photos | M2 | `gui/animations`, `gui/reference` |
| E12 Backends and SDK adapters | M3 to M5 | `backends`, `acquisition` |
| E13 Helpers | M3, M4 | `helpers` |
| E14 Knowledge base content | M4 | `knowledge-base/` |
| E15 Localisation and accessibility | M0 onward | `locale`, `gui` |

## 6. Definition of Done

1. Code passes ruff, pyright and import-linter.
2. Unit tests cover the change; analysis changes include synthetic-suite cases; helpers are tested on recorded live-view sequences.
3. User-visible strings are translated in English and Vietnamese in the same change (D-15); CI fails on a missing translation.
4. Any threshold is a named parameter with an evidence label and appears in the report's method data.
5. Connected-mode checks: no user action that the backend could perform (NFR-18).
6. Docs updated: SRS traceability if a requirement changed; TEST-CATALOGUE if a check changed.
7. CI build succeeds and `--self-test` passes on the Windows artefact.

## 7. Ways of working

- Branches: `main` protected; feature branches; pull requests with CI required.
- Commits: Conventional Commits; CHANGELOG per release.
- Versioning: SemVer for the app; schema versions independent.
- Issues: verification tasks stay in [VERIFICATION.md](VERIFICATION.md) until the maintainer opens them as issues (D-11).
- Approvals and decisions are asked in the chat, in Vietnamese (D-17).
- Hardware results: one Markdown log per body and session in `docs/hardware-log/`.

## 8. Risks to the plan

| Risk | Effect | Mitigation |
| --- | --- | --- |
| No reliable Windows PTP path | M3 slips or needs .NET helper | v0.1 does not depend on USB; helper protocol designed in P-02 |
| Helpers not feasible on some bodies (no live view or properties) | More button steps | Button fallback always exists (FR-ACQ-11); V-22 early |
| SDKs cannot be downloaded automatically for CI `[Inference]` | SDK adapters tested only on a local test machine | Run SDK tests on the maintainer's machine; mark them in CI as skipped with reason (V-23) |
| Vendor SDK terms restrict adapter code in a public repo `[Unverified]` | Adapters need to move or change | Read terms early (V-01); adapters isolated in `backends/sdk/` |
| Few openly licensed defect photos | Visual checks lack photos | Maintainer photos (D-38); drawings meanwhile |
| LibRaw lacks support for recent bodies | Checks unavailable for those models | DNG fallback (FR-META-03) |
| Thresholds wrong on real cameras | False Suspect or missed defects | Labelled parameters; calibration track; Suspect before Fail |
| Antivirus flags builds | Users cannot run the app | onedir build; Nuitka fallback; signing (O-03) |
| Single maintainer capacity | Milestones stretch | Each release stands alone |
