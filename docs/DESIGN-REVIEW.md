# Design Review: Changes and Additions to the Handoff Baseline

Status: **historical record of the first review (2026-10-16)**. Many items were later superseded or rejected (for example R-02, R-10, R-11, N-01, N-04, N-07 by D-23 to D-38). The current status of every item is in [DECISIONS.md](DECISIONS.md); the current design is in [SRS.md](SRS.md), [TEST-CATALOGUE.md](TEST-CATALOGUE.md), [ARCHITECTURE.md](ARCHITECTURE.md) and [UX.md](UX.md). Do not implement from this document.
Baseline: [archive/handoff.md](archive/handoff.md) (referred to below as "handoff", with section numbers as `H§n`).

Evidence labels follow the handoff convention: `[Sourced]`, `[Inference]`, `[Guess]`, `[Unverified]`. Nothing in this review has been run on a real camera.

## 1. Method

The handoff was reviewed against four questions:

1. Is each test logically able to detect the fault it targets?
2. Does the scope fit a personal open-source project, and is the cost of each test in proportion to its value to a buyer?
3. Are there technical, legal or usability risks the handoff does not state?
4. Is the design specific enough to implement, test and release?

A change is proposed only when it fixes a logic flaw, removes cost without losing value, or adds value at a cost that is proportionate.

## 2. Summary of revisions (R) and new features (N)

| ID | Area | Change | Why | Priority |
| --- | --- | --- | --- | --- |
| R-01 | AF, D2 | Redefine tier 1 as "focus not acquired or shutter not released within a timeout" | Under focus priority, metadata-based tier 1 cannot detect a dead point | Must |
| R-02 | Run levels | Quick level runs fully by file import; no USB or laptop needed on site | Matches the on-site constraint stated in H§11; decouples v0.1 from USB work | Must |
| R-03 | Connection | Add Windows Portable Devices (WPD) as the first candidate in the USB spike | libusb/WinUSB usually needs a driver swap that is unsafe for non-expert users | Must |
| R-04 | Run levels | Trim Standard: E1, E5 and D5 by default; full AF map and E2 to E4, E6, E7 move to Full | Removes the most laborious and least reliable steps from the common path | Should |
| R-05 | Shutter, C2/C3 | C3 at maximum aperture; C2 relative to a slow reference speed | Removes aperture-blade variance and absolute-threshold dependence | Should |
| R-06 | Dust, B4 | Drop "rotate lens on mount"; separate sensor and lens dust by comparing f/22 with f/8 frames | Avoids exposing the sensor; reuses B2 frames | Should |
| R-07 | Knowledge base | Two tiers: derived (from metadata) and curated (sourced); no test is blocked by a missing entry | Resolves the conflict between "maximum coverage" and "every entry sourced" | Must |
| R-08 | Analysis core | Analysis operates on CFA arrays plus metadata, not on files; RAW decoding isolated; DNG fallback | Testable without RAW fixtures; tolerates RAW formats unsupported by LibRaw | Must |
| R-09 | Report | JSON is canonical; self-contained HTML is rendered from it; evidence manifest with SHA-256 | Supports re-verification (H§5 principle 6) and dispute use | Must |
| R-10 | Planning | Three presets become starting points of a shot and time budget planner | Users on site have a fixed number of minutes, not a level | Should |
| R-11 | Legal | Vendor SDK adapters live outside the core repo until SDK terms are read | `[Unverified]` whether bindings written from SDK docs are allowed in a public repo | Must |
| R-12 | Structure | Package under `src/camera_preflight/`; enforced layer dependencies | H§13 layout puts modules directly under `src/`, which is not a valid package layout | Must |
| R-13 | Dependencies | No OpenCV in early milestones; NumPy and SciPy cover B1 to B6 | Smaller build, fewer licences to review | Should |
| R-14 | Acquisition | One reusable frame acceptance gate for all tests | Acceptance rules are scattered across H§6; one gate is consistent and testable | Must |
| R-15 | Sensor, B1 | Record sensor temperature where metadata exposes it; robust per-ISO statistics | Hot pixel counts depend on temperature `[Inference]`; fixed thresholds do not transfer across bodies | Should |
| N-01 | Remote | Remote pre-check pack: seller shoots a scripted set, buyer analyses it | Many used cameras are bought online; buyer cannot be on site | Should |
| N-02 | Integrity | Provenance and consistency checks on every imported frame | Prevents frames from another body being analysed; required for N-01 | Must |
| N-03 | Shutter count | Plausibility cross-check of shutter count | A reset or swapped counter is a known buyer concern `[Unverified]` | Should |
| N-04 | Import | Automatic classification of imported frames (dark, flat, chart, burst) | Lets a user drop a folder instead of labelling each file | Must |
| N-05 | Shutter | Microphone-assisted burst rhythm (C1) and sound capture (C6) | Sub-second EXIF timestamps are often absent `[Unverified]`; audio gives intervals | Could |
| N-06 | Follow-up | Baseline and compare: re-run within a return window and diff against the first report | Detects defects that appear after purchase (for example new hot pixels) | Could |
| N-07 | Field use | Field kit export: printable shooting script, group F checklist and AF chart | On-site use without a laptop (R-02) | Should |
| N-08 | UI | Bilingual UI (English and Vietnamese) from the first GUI release | Confirmed by the maintainer (D-15) | Must |
| N-09 | Onboarding | Demo mode with a synthetic sample session | Lets users rehearse before meeting a seller; doubles as test data | Could |
| N-10 | Report | Shareable single-file HTML report with hash manifest and re-verification | Buyer can send the report to a seller or repair shop; anyone with the original files can re-run the analysis and compare | Must (with R-09) |

Priority uses MoSCoW: Must, Should, Could. "Won't (this cycle)" items are listed in section 5.

## 3. Revisions in detail

### R-01 AF tier 1 redefinition

Handoff D2 counts a point as faulty when "selected point absent from the in-focus list in at least 2 of 3 shots", with AF-S, focus priority, single point and no area expansion (H§6 D0).

`[Inference]` Under focus priority the camera does not release the shutter until focus is confirmed. Every frame that exists therefore has focus confirmed at the selected point, and the in-focus list will normally contain that point. A point that never achieves focus produces no frame at all, so a metadata-based check sees nothing. The check is close to tautological. `[Unverified]` Exact behaviour per brand and AF mode must be confirmed (see V-15 in [VERIFICATION.md](VERIFICATION.md)).

Revision:

- Tier 1 signal = **focus not acquired within a timeout** (default 5 s `[Guess]`) or **shutter not released**.
  - Tethered path: capture command times out or returns a focus failure.
  - File import or manual path: the wizard shows a "camera did not focus" button per attempt; the result is recorded as user-reported.
- Metadata (Canon AF points in focus, Nikon AFInfo where a verified decoder exists) is used to **confirm which point was selected** and to reject frames where the wrong point was used. It is not used as the tier 1 signal.
- Tier 1 confidence: tethered timeout = Medium; user-reported = Low unless repeated on two lenses.

### R-02 Quick level by file import

H§11 already concludes that a buyer on site has only minutes. The implication not drawn is that a laptop, tripod and tethering are rarely available there. Revision:

- Quick runs entirely by **file import**: the user follows a printed or on-screen shooting script (N-07), then loads the card through a card reader or the camera's mass-storage mode.
- Quick content: step 0 reduced (identify from metadata), A1 from metadata, A3, reduced F, B1 (two configurations), B2, B4, C1 (burst), D5 optional (only if a tripod is available, otherwise skipped with reason).
- C3 (handoff Quick) is replaced by C1: C3 needs flicker-free, stable light that is rarely available on site, while a burst needs no setup and is a standard buyer check `[Sourced]`.
- Consequence for the plan: release v0.1 needs no USB backend. USB moves after v0.1 (see [ROADMAP.md](ROADMAP.md)).

### R-03 Windows USB strategy

`[Sourced]` FC.SDK uses LibUsbDotNet with WinUSB on Windows (H§4). `[Inference]` Using libusb against a camera on Windows usually requires replacing the default driver (for example with Zadig). This disables normal Explorer access to the camera until reverted, and is error-prone for a buyer using a seller's camera.

Revision: the USB spike evaluates, in this order:

1. **WPD** (Windows Portable Devices, the API behind the default camera driver), through COM from Python (`comtypes`) or a small .NET helper. `[Unverified]` Whether WPD passes vendor PTP operations (for example Canon 0xD1AC) through its MTP extension commands. This is verification task V-13.
2. libusb with WinUSB, only with an explicit, reversible driver-install step in the UI.
3. .NET helper around FC.SDK (handoff fallback).

### R-04 Trimmed Standard level

- Group E needs stable, even light that buyers rarely control. E1 (consistency) and E5 (compensation linearity) carry most of the value and stay in Standard. E2, E3, E4, E6 and E7 move to Full.
- Group D in Standard: selecting every AF point by hand on a DSLR (for example 61 points x 3 repeats = 183 manual selections) is not realistic, and only Canon metadata reliably confirms the selected point `[Sourced]`. Standard uses D5 (centre plus four outermost points) by default; the full point map is opt-in.

### R-05 Shutter tests

- C3 repeatability: shoot at **maximum aperture**. `[Inference]` At stopped-down apertures, aperture blade repeatability adds to the spread and is attributed to the shutter by mistake.
- C2 uniformity: compare the brightness gradient at each fast speed with the gradient at a **slow reference speed** (for example 1/30, which spans several flicker cycles of 100 Hz or 120 Hz lighting `[Inference]`). The reference absorbs lens vignetting and uneven lighting, so only the speed-dependent component is attributed to the curtain.

### R-06 Dust test without lens rotation

Handoff B4 rotates the lens on the mount between frames. `[Inference]` This briefly opens the mount, can admit new dust, and is risky on a seller's camera. Revision: at f/16 to f/22, sensor dust casts sharp shadows; at f/8 the same marks are faint or invisible. Comparing B4 (f/22) with B2 (f/8) frames classifies marks as sensor-side without touching the mount. Lens rotation remains an optional manual step in Full.

### R-07 Two-tier knowledge base

The handoff wants maximum model coverage (decision 5) and also requires every entry to have a source and a confirming test (H§9). These conflict for a single maintainer.

- **Derived tier**: fields read from metadata of the user's own frames (model, AF point count and positions where exposed, firmware version, lens). Generated automatically, stored in the session, never presented as curated.
- **Curated tier**: YAML entries with source and confidence (rated shutter life, latest firmware, known issues, verified AF decoder flag).
- Rule: a missing curated entry lowers confidence or marks individual checks Not tested with reason "no reference data"; it never blocks the whole test.

### R-08 Analysis on CFA arrays

- The analysis layer accepts a `Frame` (CFA array, black and white levels, CFA pattern, metadata, provenance) and never opens files. RAW decoding is a separate adapter (rawpy/LibRaw).
- Unit tests use synthetic CFA arrays with injected defects, so no RAW files are committed.
- RAW format not supported by the bundled LibRaw: the app suggests converting to DNG with a vendor tool `[Unverified]` that the bundled LibRaw reads such DNG files. JPEG input is accepted only for tests where processing does not hide the defect, and with Low confidence.

### R-09 Report format

- `report.json` (schema-versioned) is the record. `report.html` is rendered from it as one self-contained file.
- An evidence manifest lists every source file and evidence image with SHA-256. The report header shows the manifest hash.
- PDF export is deferred; the HTML prints cleanly.

### R-10 Budget planner

The three presets (Quick, Standard, Full) become starting selections. The plan screen shows planned shots, estimated minutes `[Guess]` per test, and shutter actuations as a share of rated life when known. The user may set a shot budget and a time budget; the planner drops the lowest value-per-cost tests first and shows what was dropped.

### R-11 SDK adapters out of the core repo

`[Unverified]` Whether vendor SDK terms allow publishing bindings (headers, `ctypes` declarations, wrappers) in a public repo. Until V-01 is resolved, the core defines a backend plugin interface (Python entry points) and ships no SDK-specific code. An adapter can live in a separate repo or remain private.

### R-12 Package layout

Use `src/camera_preflight/<subpackage>`. Layer dependencies are enforced by an import contract checked in CI (see [ARCHITECTURE.md](ARCHITECTURE.md)).

### R-13 Dependency minimisation

B1 to B6 need neighbourhood statistics, high-pass filtering, labelling of connected blobs and per-region means. `[Inference]` NumPy and SciPy (`scipy.ndimage`) cover all of these. OpenCV is added only if a later test needs it (for example chart registration for D6).

### R-14 Frame acceptance gate

A single component evaluates every frame before analysis. Rules come from the test definition and include: correct exposure settings (ISO, shutter, aperture, NR off), histogram range, clipping, flicker banding, provenance (N-02), and the selected AF point for group D. A rejected frame is kept as evidence with the reason and is never analysed.

### R-15 Sensor temperature and robust statistics

- `[Inference]` Hot pixel counts rise with sensor temperature. Where metadata exposes a temperature (for example Canon `CameraTemperature` `[Unverified]`), it is recorded and shown next to B1 results.
- B1 and B2 detection uses robust statistics per CFA channel (median and median absolute deviation of local residuals), computed separately per ISO and exposure time.

## 4. New features in detail

### N-01 Remote pre-check pack

Flow: the buyer generates a pack (shooting script as a printable page plus a short text version for messaging apps). The seller shoots the scripted frames and sends the original files. The buyer imports them.

Safeguards:

- All frames pass N-02 provenance checks. Any frame that fails is excluded and the report says so.
- Every result from a remote pack is capped at Medium confidence and labelled "seller-supplied frames".
- The report never states that a remote check replaces an in-person inspection.

### N-02 Provenance and consistency checks

Per frame and per session:

- Body serial in maker notes is identical across frames and, if the user typed the body serial, matches it.
- Capture times fall within the session window (or the declared remote window) and are monotonic with file numbers.
- No editing software tag in metadata; maker notes present; RAW dimensions match the model. `[Inference]` These are indicators, not proof.
- Results: consistent, inconsistent (frame excluded), or unknown (field not available; lowers confidence).

### N-03 Shutter count plausibility

Cross-checks, each shown separately with its basis:

- Shutter count versus the file-number counter (when the user has not reset it).
- Count versus model release date (actuations per year), flagged only when far outside a broad range `[Guess]`.
- Count across frames of the same session: must increase by exactly the number of actuations taken.
- Output is "consistent" or "worth asking the seller about". It never concludes tampering.

### N-04 Automatic frame classification

Classify imported frames by metadata and statistics: dark (very low mean, body cap), flat (low spatial variance, mid histogram), chart (high-frequency content), burst (sequence of short intervals), other. The user confirms or corrects the classification on one screen.

### N-05 Microphone-assisted burst rhythm

During C1 the app records audio from the PC microphone and detects shutter onsets. Intervals give frame rate and stalls without relying on sub-second EXIF timestamps. Optional; needs the tethered path or the user starting the recording manually. `[Unverified]` Detection precision in a noisy room (V-18).

### N-06 Baseline and compare

A saved session can be re-run later with the same plan. The comparison shows new or vanished defective pixels, dust changes, and shutter count delta. Useful within a return window.

### N-07 Field kit export

One printable HTML page per plan: shooting script with camera settings per step, group F checklist with tick boxes, and the AF chart (generated per model when layout data exists, generic otherwise).

### N-08 Bilingual UI (confirmed, D-15)

Qt translation files (`.ts`) for English and Vietnamese from the first GUI release. Reports use the UI language, with test IDs and verdict codes language-neutral.

### N-09 Demo mode

A bundled synthetic session (generated CFA frames with known injected defects) that users can run end to end. The same generator produces the test fixtures, so the demo is always consistent with the test suite.

### N-10 Shareable report with hash manifest

Covered with R-09. The HTML embeds evidence images and the manifest hash. A hash stored inside the same file does not prove the report was not edited: anyone can change the content and recompute it. What the manifest does provide is a link to the original files: a recipient with those files can recompute the hashes and re-run the analysis with the stated app version and parameter set (FR-REP-08). Results are trustworthy because they can be reproduced, not because of the hash. Digital signatures are not proposed: a self-generated key on a personal PC proves no identity `[Inference]`.

## 5. Considered and not proposed this cycle

| Idea | Reason not proposed |
| --- | --- |
| Mobile companion app | Doubles platform work; N-07 field kit covers the on-site need |
| Wi-Fi connection backends | Adds a second transport per brand; USB and file import cover the scope |
| Automatic buy or price advice | Out of scope by maintainer decision (H§9) |
| Absolute shutter speed measurement | Needs a reference instrument (H§6 C5) |
| Cloud upload or shared defect database | Privacy and hosting cost; reconsider once reports are stable |
| Lens-only inspection profile | Valuable but widens scope; revisit after v0.3 |

## 6. Items kept unchanged

Stack (Python, PySide6), four result levels, AF and metering as Suspect with confidence, relative comparisons over absolute thresholds, no bundled SDK, no reading of previous-owner personal data, Apache-2.0, onedir packaging, CI release builds from the first milestone.
