# Test Catalogue

Revision of handoff section 6 ([archive/handoff.md](archive/handoff.md)) with the design review ([DESIGN-REVIEW.md](DESIGN-REVIEW.md)) and maintainer decisions D-23 to D-45 ([DECISIONS.md](DECISIONS.md)) applied. Profiles were removed (D-28): every applicable check is always in the wizard, ordered by automation level (section 9). Revised items are marked with their review ID. Evidence labels keep the handoff meaning. Nothing here has been run on a real camera. Thresholds marked `[Guess]` are parameters to be calibrated (V-07), not facts.

## 0. Conventions

- **Paths**: T = connected, run by the app; SA = semi-automatic (user acts, app does the rest); FI = upload mode (from uploaded files); M = manual.
- **Shots**: maximum actuations a check may cause. A design limit only; the app shows no shot estimate or counter (D-32).
- **Gate**: acceptance rules applied to each frame before analysis (section 1).

## 1. Frame acceptance gate (R-14)

Every capture step declares a gate profile. Common rules:

| Rule | Check | Applies to |
| --- | --- | --- |
| G1 Settings | ISO, shutter, aperture, file type (RAW), long-exposure NR and high-ISO NR off, as required by the step | All |
| G2 Histogram | Mean and percentiles of each CFA channel within the step's range | Flat, chart, metering |
| G3 Clipping | Share of pixels at white level below a limit (0.01% `[Guess]`) | Flat, chart, metering |
| G4 Flicker | Periodic row-mean banding along the shutter travel axis below a limit; banding that changes phase between frames is flicker | Flat frames at 1/250 or faster |
| G5 Provenance | Same body serial; capture time in window; file-number order; no editing tag (N-02) | All |
| G6 AF point | Selected AF point in metadata equals the requested point, where a verified decoder exists | Group D |
| G7 Darkness | Dark frame mean close to black level; no light leak gradient | Dark frames |

A rejected frame is stored with the failed rule and is not analysed.

## 2. Preparation

Equipment (handoff table retained; changes noted):

| Item | Used for | Note |
| --- | --- | --- |
| Known-good USB cable, full battery or external power | Tethered paths | `[Guess]` weak battery or cable can drop the session |
| Known-good memory card, empty | All | Separate from the previous owner's card |
| Card reader | Upload mode | To copy files to the PC |
| Flat grey or white target, even continuous light | B, C, E | Daylight from an overcast sky or halogen light; avoid LED and fluorescent `[Inference]` |
| Body cap | B1 | |
| AF chart (provided by the app as a file to print or show on a screen), tripod | D, E3 | Without them, D and E3 are skipped by the user |
| Reference lens and a second lens | D10, E7 | `[Sourced]` separates body from lens faults |
| Windows PC | Both modes | |

### Step 0 Initial survey

| Step | Action | Path |
| --- | --- | --- |
| 0.1 | Identify brand, model, serial, firmware from USB (T) or the first frame's metadata (FI) | T, FI |
| 0.2 | Choose backend: SDK adapter, PTP, file import | T |
| 0.3 | Show required USB mode and conflicting settings `[Sourced]` | T |
| 0.4 | Record current settings (ISO, quality, NR, AF fine-tune if readable `[Sourced]` for Nikon); store originals for restore (FR-ACQ-06) | T, FI |
| 0.5 | Set capture conditions: RAW, NR off, lens corrections off `[Inference]`; done by the app, guided manual step only if a setting cannot be written | T; upload mode: shown as parameters |
| 0.6 | One test frame: verify RAW decodes and metadata reads; if not, demote affected tests and say why | T, FI |

## 3. Group A: identification and camera data

| Test | Action | Verdict | Paths |
| --- | --- | --- | --- |
| A1 Identification | Read model, firmware, serial (device info or metadata); compare with user-entered serial | Mismatch or unreadable = Suspect, Medium | T: Canon `[Sourced]`, Nikon, Sony `[Unverified]`; FI |
| A2 Battery | Read battery level | Record only; wear not measurable; manual timing optional | T: Canon `[Sourced]` |
| A3 Shutter count | Canon PTP 0xD1AC up to about DIGIC 5 `[Sourced]`; newer Canon `[Unverified]` (V-05); Nikon, Sony from EXIF `[Sourced]` | Share of rated life when known; "unreadable", never 0; plausibility checks (N-03) shown separately | T, FI |
| A4 Firmware | Compare version with curated KB latest | Older = warning (not Suspect) | T, FI |
| A5 Storage | List cards, capacity, file count; test each slot | Card not recognised or slot fault = Suspect | T |
| A6 Mounted lens | Lens info from metadata | Record; becomes the reference lens for D | FI, T |
| A7 Previous owner traces | Guide through owner name, copyright, saved Wi-Fi menus | Reminder to clear; app reads nothing (CON-05) | M |

## 4. Group B: sensor

Analysis is brand independent and runs on CFA arrays per channel (R-08). Detection statistics are robust (median and MAD of local residuals), computed per ISO and exposure (R-15).

| Test | Setup and capture | Analysis | Verdict | Shots |
| --- | --- | --- | --- | --- |
| B1 Dark frame | Body cap; long-exposure NR off; base ISO, 1600 and 6400 at 1/100 s and 30 s (bulb where available), 3 frames each `[Guess]` | Pixels with residual above k x MAD versus same-channel neighbours; "hot" = at the same coordinates in all frames of the set (3 `[Inference]`: in simulation, 2 of 3 let random single-electron events through at high ISO; parameter `b1.repeat_min`); record sensor temperature if available | Cluster of adjacent defects = High; isolated defects counted against a per-megapixel allowance `[Guess]`; none = Pass with note that firmware may map out pixels `[Inference]` | 18 |
| B2 Flat frame | Target defocused, f/8, histogram mean 50 to 80% of range, no clipping; 3 frames with slight target shift | Pixels deviating from same-channel neighbours at the same coordinates in all frames | Stuck dark or stuck bright; same scale as B1 | 3 |
| B3 Classification | Uses B1 and B2 | Dead (dark in flat), stuck bright (bright in all), hot (bright with exposure time), per channel R, G1, G2, B with coordinates `[Inference]` | Report only; severity inherited from B1, B2 | 0 |
| B4 Dust and marks (R-06) | Flat target, f/16 to f/22, strongly defocused; 3 frames | High-pass filter, blob labelling; compare with B2 (f/8): marks sharp at f/22 and faint at f/8 = sensor-side `[Inference]`; linear marks may indicate a scratch `[Sourced]` | Count, size, region map; linear mark = Suspect, High; heavy dust = Medium | 3 |
| B5 Uniformity | Reuse B2 frames | Brightness grid per channel; stripes, boundaries, colour casts; left-right vignette symmetry `[Sourced]` | Anomaly = Suspect with heat map | 0 |
| B6 Noise and banding | Reuse B1 frames | Standard deviation per channel and ISO; row and column banding | Report banding; compare noise only with curated reference data if present `[Inference]` | 0 |

## 5. Group C: shutter

Absolute speed is not measured (C5). The light source must be flicker-free for C2 and C3 (gate G4).

| Test | Action | Analysis | Verdict | Shots |
| --- | --- | --- | --- | --- |
| C1 Burst rhythm | 10 frames at the highest burst speed | Intervals from sub-second EXIF timestamps (V-17); optional audio onsets (N-05); compare with rated speed when in KB | Stall or large variation = Suspect `[Sourced]` buyer checklists recommend burst testing | 10 |
| C2 Curtain uniformity (R-05) | Flat frames at a slow reference speed (1/30 `[Inference]`) and at 1/250, 1/1000, 1/4000, fastest; 3 frames each | Row and column mean profiles; subtract the reference profile; remaining gradient along the travel axis | Gradient above limit `[Guess]` = Suspect; periodic stripes that shift between frames = flicker, frame rejected | 15 |
| C3 Repeatability (R-05) | 10 identical frames, flat target, maximum aperture | Spread of mean RAW level in EV | Spread above 0.1 EV `[Guess]` = Suspect | 10 |
| C4 Mechanical versus electronic | If EFCS or electronic shutter exists, repeat C2 fast speeds in that mode | Compare with C2 | Fault only in mechanical = suspect curtain; in both = suspect sensor or light `[Inference]` | 12 |
| C5 Absolute speed | Not measured | Needs reference instrument | Not tested, reason "requires reference instrument" | 0 |
| C6 Sound and mirror | Guided listening; optional audio recording (N-05) | User judgement | Manual (group F) | 0 |

## 6. Group D: autofocus

Two tiers (D-04): tier 1 = point does not achieve focus; tier 2 = point achieves focus but the result is soft or off. All conclusions are Suspect with confidence (D-03).

### D0 Protocol

- App-provided chart (`guide` package; printed or shown on a screen) perpendicular to the camera, on a tripod, flicker-free light.
- AF-S with focus priority, single point, area expansion off `[Sourced]`.
- Before each shot, defocus fully so the camera must refocus `[Sourced]` (manual focus ring to the near limit, or SDK drive where available).
- DSLR: optical viewfinder path, not Live View `[Sourced]`.
- Fixed reference lens per session; record AF fine-tune if readable.
- Tier 1 signal (R-01): focus not acquired or shutter not released within 5 s `[Guess]`. Tethered: capture timeout or focus failure. File import or manual: user presses "camera did not focus" for that attempt. Behaviour per brand to confirm (V-15).

| Test | Action | Analysis and verdict | Paths | Shots |
| --- | --- | --- | --- | --- |
| D1 AF point map | Point count, type, layout from curated KB, else derived from metadata (Canon `[Sourced]`) | Drives chart and point list; unknown layout = generic 5-point plan only | KB, FI | 0 |
| D2 Tier 1 (R-01) | Select each point; 3 attempts (parameter `af.attempts`, `[Guess]`) | Point fails to focus in at least 2 of 3 attempts = Suspect; tethered timeout Medium confidence, user-reported Low; metadata confirms selected point (gate G6) only where decoder verified | T, SA, M | Points x repeats |
| D3 Tier 2 | Reuse accepted D2 or D5 frames | Edge contrast around each point versus the centre point in the same session `[Sourced]`; prioritise left and right edge points `[Sourced]` | FI, T | 0 |
| D4 Repeatability | Reuse D2/D3 data | Large spread of sharpness across repeats = unstable AF = Suspect `[Inference]` | FI, T | 0 |
| D5 Priority sample | Centre plus four outermost points first, 3 attempts each `[Sourced]` sampling; the remaining points follow in the same run | Early D2 to D4 results on 5 points | T, SA, FI | 15 |
| D6 Mirrorless by region | Grid of regions; per region: set AF area, focus, shoot, measure sharpness | Sharpness heat map; no per-point fault | Sony SDK `[Sourced]`; Canon EDSDK `[Sourced]`; Nikon `[Unverified]` | Regions x 3 |
| D7 AF response time | Half-press to focus confirmation | Long time versus model reference = Suspect `[Inference]` | Sony SDK `[Sourced]`; others `[Unverified]` | Included in D6 |
| D8 Absolute focus position | Drive to preset, read back | Not reached or offset = Suspect | Sony SDK `[Sourced]` | 0 to 5 |
| D9 AF fine-tune | Read value | Non-zero = warning; repeat D3 with it off `[Inference]` | Nikon metadata `[Sourced]`; others `[Unverified]` | 0 |
| D10 Body or lens | Repeat D2/D3 with the second lens, suspect points first | Fault with one lens = lens; with both = body `[Sourced]` | As D2 | As D2/D5 |

AF verdict rules (handoff retained):

- Fail only when the fault repeats across attempts and with both lenses.
- A few mildly off points are normal `[Sourced]`: mild Suspect, Low severity.
- Centre point faults carry higher severity `[Inference]`.
- Report: AF point map coloured by result level with icons.

## 7. Group E: metering and exposure

Consistency and linearity only. In connected mode all E checks run inside the flat-field group (section 9, row 3b), except E3.

| Test | Action | Analysis | Verdict | Shots |
| --- | --- | --- | --- | --- |
| E1 Consistency | Even grey scene; P or Av; fixed ISO; 5 frames | Exposure chosen by camera from EXIF | Spread over 1/3 EV `[Guess]` = Suspect | 5 |
| E2 Between modes | Evaluative, centre-weighted, spot on a uniform scene | Compare exposures | Large deviation = Suspect `[Inference]` | 3 |
| E3 Spot position | Bright and dark regions; move bright region; spot metering | Exposure follows the measured region | No change = Suspect `[Inference]` | 3 |
| E4 Output level | Reuse E1 | Mean RAW level versus nominal mid-grey | Report only; offset may be by design `[Inference]` | 0 |
| E5 Compensation linearity | -2 to +2 EV, 5 frames | Output steps should be even | Clear nonlinearity = Suspect `[Inference]` | 5 |
| E6 ISO linearity | Fixed shutter and aperture, ISO steps | RAW level after black subtraction per step | Abnormal jump = Suspect `[Inference]` | 5 |
| E7 Aperture steps | Fixed shutter and ISO, aperture steps | Even brightness fall | Abnormal step = suspect blades or lens; cross-check D10 | 5 |

## 8. Group F: physical and manual checks

Handoff list retained. Each item: Pass, Suspect, Fail or Not tested, with notes and optional photo (path = manual).

- **Blocker check (first, D-35)**: powers on normally; no crack or large dent; mount not deformed; mirror not stuck (DSLR). Yes/no answers with reference photos.
- **Manual checks (last, D-34)**: body and structure; controls (list per model from KB, generic list otherwise); displays and finder with exported solid-colour images; mirror and shutter sounds (C6); flash and sync; power and ports; Wi-Fi and Bluetooth enable; 10 s video with audio; bundled lens condition `[Sourced]`.

Blocker candidates: no power; stuck mirror; clearly scratched sensor.

## 9. Execution plan by automation level (D-34, D-35)

Levels: **Auto** = runs, marks and advances alone. **Semi-H** = semi-automatic, started by a helper ([UX.md](UX.md) section 3.3). **Semi-B** = semi-automatic, started by a button. **Upload** = user shoots with the shown parameters and uploads; the app validates and analyses. **Manual** = user judges.

| Order | Phase | Checks | Connected mode | Upload mode |
| --- | --- | --- | --- | --- |
| 1 | Blocker check | Powers on normally; no crack or large dent; mount not deformed; mirror not stuck (DSLR) | Manual | Manual |
| 2 | Automatic | A1 identification and serial; A2 battery; A3 shutter count (before); A4 firmware; A5 storage per slot; settings applied (RAW, NR off, corrections off); test frame decodes; D9 AF fine-tune read; C1 burst rhythm (any scene) | Auto | A1, A3, A4, A6, D9 from the first uploaded frame; C1 Upload |
| 3a | Semi: dark | B1 dark frames (all ISO and exposure configurations), B3, B6 | Semi-H (H1: cap fitted, viewfinder covered) | Upload |
| 3b | Semi: flat field | B2, B4, B5, C2, C3, C4, E1, E2, E4, E5, E6, E7 in one run; the app changes aperture, speed, ISO, metering and shutter modes itself | Semi-H (H2: even bright field, defocused; H6 for MF where readable, else Semi-B) | Upload, one step per check |
| 3c | Semi: chart | E3 spot metering; D1 to D5 AF on all points; D6 to D8 where an SDK allows | Semi-H (H3 chart in view, H4 steady); AF point selection by the app where the backend supports it, else Semi-B per point | Upload, one step per point group |
| 3d | Semi: second lens | D10, E7 repeat | Semi-H (H5 lens changed) | Upload |
| 4 | Manual | Full physical list (group F), C6 sound, A7 previous-owner traces | Manual, with reference photos | Manual, with reference photos |
| 5 | Results | Summary, details, A3 shutter count after the session, HTML report, restore settings | Auto | Auto |

Notes:

- `[Unverified]` Remote AF point selection for optical viewfinder AF and focus drive depend on the backend and SDK (V-03, V-04). Where unavailable, the AF run becomes Semi-B per point: the user selects the point with the joystick and presses the button; the app does the rest.
- Checks that need an unconfigured SDK are Not tested, reason "SDK not configured" (D-24).
- In upload mode each step lists the exact parameters; uploads that do not meet them are rejected with the reason (D-30).
