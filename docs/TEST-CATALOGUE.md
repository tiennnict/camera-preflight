# Test Catalogue

Revision of handoff section 6 ([archive/handoff.md](archive/handoff.md)) with the design review applied ([DESIGN-REVIEW.md](DESIGN-REVIEW.md)). Revised items are marked with their review ID. Evidence labels keep the handoff meaning. Nothing here has been run on a real camera. Thresholds marked `[Guess]` are parameters to be calibrated (V-07), not facts.

## 0. Conventions

- **Profiles**: Q = Quick, S = Standard, F = Full. "opt" = available but not selected by default.
- **Paths**: T = tethered automatic, SA = semi-automatic (user acts, app reads the result), FI = file import, M = manual.
- **Shots**: maximum actuations the test may cause, excluding re-shoots of rejected frames (re-shoots are counted and reported separately).
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
| Card reader | FI path | New: needed for Quick by file import (R-02) |
| Flat grey or white target, even continuous light | B, C, E | Daylight from an overcast sky or halogen light; avoid LED and fluorescent `[Inference]` |
| Body cap | B1 | |
| Printed AF chart (field kit), tripod | D | Without a tripod, D is skipped in Quick |
| Reference lens and a second lens | D10, E7 | `[Sourced]` separates body from lens faults |
| Windows PC | T and FI paths | Not needed on site for Quick |

### Step 0 Initial survey

| Step | Action | Path |
| --- | --- | --- |
| 0.1 | Identify brand, model, serial, firmware from USB (T) or the first frame's metadata (FI) | T, FI |
| 0.2 | Choose backend: SDK adapter, PTP, file import | T |
| 0.3 | Show required USB mode and conflicting settings `[Sourced]` | T |
| 0.4 | Record current settings (ISO, quality, NR, AF fine-tune if readable `[Sourced]` for Nikon); store originals for restore (FR-ACQ-06) | T, FI |
| 0.5 | Set capture conditions: RAW, NR off, lens corrections off `[Inference]` | T, M |
| 0.6 | One test frame: verify RAW decodes and metadata reads; if not, demote affected tests and say why | T, FI |

## 3. Group A: identification and camera data

| Test | Action | Verdict | Paths | Profiles |
| --- | --- | --- | --- | --- |
| A1 Identification | Read model, firmware, serial (device info or metadata); compare with user-entered serial | Mismatch or unreadable = Suspect, Medium | T: Canon `[Sourced]`, Nikon, Sony `[Unverified]`; FI | Q S F |
| A2 Battery | Read battery level | Record only; wear not measurable; manual timing optional | T: Canon `[Sourced]` | S F |
| A3 Shutter count | Canon PTP 0xD1AC up to about DIGIC 5 `[Sourced]`; newer Canon `[Unverified]` (V-05); Nikon, Sony from EXIF `[Sourced]` | Share of rated life when known; "unreadable", never 0; plausibility checks (N-03) shown separately | T, FI | Q S F |
| A4 Firmware | Compare version with curated KB latest | Older = warning (not Suspect) | T, FI | S F |
| A5 Storage | List cards, capacity, file count; test each slot | Card not recognised or slot fault = Suspect | T | S F |
| A6 Mounted lens | Lens info from metadata | Record; becomes the reference lens for D | FI, T | Q S F |
| A7 Previous owner traces | Guide through owner name, copyright, saved Wi-Fi menus | Reminder to clear; app reads nothing (CON-05) | M | S F |

## 4. Group B: sensor

Analysis is brand independent and runs on CFA arrays per channel (R-08). Detection statistics are robust (median and MAD of local residuals), computed per ISO and exposure (R-15).

| Test | Setup and capture | Analysis | Verdict | Shots | Profiles |
| --- | --- | --- | --- | --- | --- |
| B1 Dark frame | Body cap; long-exposure NR off; Q: base ISO and ISO 1600 at 1 s, 3 frames each `[Guess]`; S/F: base, 1600, 6400 at 1/100 s and 30 s (bulb where available), 3 frames each | Pixels with residual above k x MAD versus same-channel neighbours; "hot" = at the same coordinates in at least 2 of 3 frames; record sensor temperature if available | Cluster of adjacent defects = High; isolated defects counted against a per-megapixel allowance `[Guess]`; none = Pass with note that firmware may map out pixels `[Inference]` | Q 6, S/F 18 | Q S F |
| B2 Flat frame | Target defocused, f/8, histogram mean 50 to 80% of range, no clipping; 3 frames with slight target shift | Pixels deviating from same-channel neighbours at the same coordinates in all frames | Stuck dark or stuck bright; same scale as B1 | 3 | Q S F |
| B3 Classification | Uses B1 and B2 | Dead (dark in flat), stuck bright (bright in all), hot (bright with exposure time), per channel R, G1, G2, B with coordinates `[Inference]` | Report only; severity inherited from B1, B2 | 0 | Q S F |
| B4 Dust and marks (R-06) | Flat target, f/16 to f/22, strongly defocused; 3 frames | High-pass filter, blob labelling; compare with B2 (f/8): marks sharp at f/22 and faint at f/8 = sensor-side `[Inference]`; linear marks may indicate a scratch `[Sourced]` | Count, size, region map; linear mark = Suspect, High; heavy dust = Medium | 3 | Q S F |
| B5 Uniformity | Reuse B2 frames | Brightness grid per channel; stripes, boundaries, colour casts; left-right vignette symmetry `[Sourced]` | Anomaly = Suspect with heat map | 0 | S F |
| B6 Noise and banding | Reuse B1 frames | Standard deviation per channel and ISO; row and column banding | Report banding; compare noise only with curated reference data if present `[Inference]` | 0 | S F |

## 5. Group C: shutter

Absolute speed is not measured (C5). The light source must be flicker-free for C2 and C3 (gate G4).

| Test | Action | Analysis | Verdict | Shots | Profiles |
| --- | --- | --- | --- | --- | --- |
| C1 Burst rhythm | 10 frames at the highest burst speed | Intervals from sub-second EXIF timestamps (V-17); optional audio onsets (N-05); compare with rated speed when in KB | Stall or large variation = Suspect `[Sourced]` buyer checklists recommend burst testing | 10 | Q S F |
| C2 Curtain uniformity (R-05) | Flat frames at a slow reference speed (1/30 `[Inference]`) and at 1/250, 1/1000, 1/4000, fastest; 3 frames each | Row and column mean profiles; subtract the reference profile; remaining gradient along the travel axis | Gradient above limit `[Guess]` = Suspect; periodic stripes that shift between frames = flicker, frame rejected | 15 | S F |
| C3 Repeatability (R-05) | 10 identical frames, flat target, maximum aperture | Spread of mean RAW level in EV | Spread above 0.1 EV `[Guess]` = Suspect | 10 | S F |
| C4 Mechanical versus electronic | If EFCS or electronic shutter exists, repeat C2 fast speeds in that mode | Compare with C2 | Fault only in mechanical = suspect curtain; in both = suspect sensor or light `[Inference]` | 12 | S F (if available) |
| C5 Absolute speed | Not measured | Needs reference instrument | Not tested, reason "requires reference instrument" | 0 | - |
| C6 Sound and mirror | Guided listening; optional audio recording (N-05) | User judgement | Manual (group F) | 0 | S F |

## 6. Group D: autofocus

Two tiers (D-04): tier 1 = point does not achieve focus; tier 2 = point achieves focus but the result is soft or off. All conclusions are Suspect with confidence (D-03).

### D0 Protocol

- App-generated chart (field kit) perpendicular to the camera, on a tripod, flicker-free light.
- AF-S with focus priority, single point, area expansion off `[Sourced]`.
- Before each shot, defocus fully so the camera must refocus `[Sourced]` (manual focus ring to the near limit, or SDK drive where available).
- DSLR: optical viewfinder path, not Live View `[Sourced]`.
- Fixed reference lens per session; record AF fine-tune if readable.
- Tier 1 signal (R-01): focus not acquired or shutter not released within 5 s `[Guess]`. Tethered: capture timeout or focus failure. File import or manual: user presses "camera did not focus" for that attempt. Behaviour per brand to confirm (V-15).

| Test | Action | Analysis and verdict | Paths | Shots | Profiles |
| --- | --- | --- | --- | --- | --- |
| D1 AF point map | Point count, type, layout from curated KB, else derived from metadata (Canon `[Sourced]`) | Drives chart and point list; unknown layout = generic 5-point plan only | KB, FI | 0 | S F |
| D2 Tier 1 (R-01) | Select each point; 3 attempts (S) or 5 (F) | Point fails to focus in at least 2 of 3 attempts = Suspect; tethered timeout Medium confidence, user-reported Low; metadata confirms selected point (gate G6) only where decoder verified | T, SA, M | Points x repeats | F (all points) |
| D3 Tier 2 | Reuse accepted D2 or D5 frames | Edge contrast around each point versus the centre point in the same session `[Sourced]`; prioritise left and right edge points `[Sourced]` | FI, T | 0 | S (D5 points), F |
| D4 Repeatability | Reuse D2/D3 data | Large spread of sharpness across repeats = unstable AF = Suspect `[Inference]` | FI, T | 0 | S F |
| D5 Reduced sample | Centre plus four outermost points, 3 attempts each `[Sourced]` sampling | D2 to D4 on 5 points | T, SA, FI | 15 | Q (opt, tripod), S |
| D6 Mirrorless by region | Grid of regions; per region: set AF area, focus, shoot, measure sharpness | Sharpness heat map; no per-point fault | Sony SDK `[Sourced]`; Canon EDSDK `[Sourced]`; Nikon `[Unverified]` | Regions x 3 | F |
| D7 AF response time | Half-press to focus confirmation | Long time versus model reference = Suspect `[Inference]` | Sony SDK `[Sourced]`; others `[Unverified]` | Included in D6 | F |
| D8 Absolute focus position | Drive to preset, read back | Not reached or offset = Suspect | Sony SDK `[Sourced]` | 0 to 5 | F |
| D9 AF fine-tune | Read value | Non-zero = warning; repeat D3 with it off `[Inference]` | Nikon metadata `[Sourced]`; others `[Unverified]` | 0 | S F |
| D10 Body or lens | Repeat D5 (S opt) or D2/D3 (F) with second lens | Fault with one lens = lens; with both = body `[Sourced]` | As D2 | As D2/D5 | F, S opt |

AF verdict rules (handoff retained):

- Fail only when the fault repeats across attempts and with both lenses.
- A few mildly off points are normal `[Sourced]`: mild Suspect, Low severity.
- Centre point faults carry higher severity `[Inference]`.
- Report: AF point map coloured by result level with icons.

## 7. Group E: metering and exposure

Consistency and linearity only. R-04: E1 and E5 in Standard; the rest in Full.

| Test | Action | Analysis | Verdict | Shots | Profiles |
| --- | --- | --- | --- | --- | --- |
| E1 Consistency | Even grey scene; P or Av; fixed ISO; 5 frames | Exposure chosen by camera from EXIF | Spread over 1/3 EV `[Guess]` = Suspect | 5 | S F |
| E2 Between modes | Evaluative, centre-weighted, spot on a uniform scene | Compare exposures | Large deviation = Suspect `[Inference]` | 3 | F |
| E3 Spot position | Bright and dark regions; move bright region; spot metering | Exposure follows the measured region | No change = Suspect `[Inference]` | 3 | F |
| E4 Output level | Reuse E1 | Mean RAW level versus nominal mid-grey | Report only; offset may be by design `[Inference]` | 0 | F |
| E5 Compensation linearity | -2 to +2 EV, 5 frames | Output steps should be even | Clear nonlinearity = Suspect `[Inference]` | 5 | S F |
| E6 ISO linearity | Fixed shutter and aperture, ISO steps | RAW level after black subtraction per step | Abnormal jump = Suspect `[Inference]` | 5 | F |
| E7 Aperture steps | Fixed shutter and ISO, aperture steps | Even brightness fall | Abnormal step = suspect blades or lens; cross-check D10 | 5 | F |

## 8. Group F: physical and manual checks

Handoff list retained. Each item: Pass, Suspect, Fail or Not tested, with notes and optional photo (path = manual).

- **Reduced F (Quick, and first in every plan)**: powers on; no error message; mirror and shutter fire (DSLR); LCD shows image; no visible sensor scratch on a quick look; card slot accepts card; lens mounts and locks.
- **Full F (Standard, Full)**: body and structure; controls (list per model from KB, generic list otherwise); displays and finder with exported solid-colour images; mirror and shutter sounds (C6); flash and sync; power and ports; Wi-Fi and Bluetooth enable; 10 s video with audio; bundled lens condition `[Sourced]`.

Blocker candidates: no power; stuck mirror; clearly scratched sensor.

## 9. Profiles and shot estimates

All figures `[Guess]`, recomputed from the tables above. N = number of AF points.

| Profile | Content | Shots (approx.) | Minutes (approx.) |
| --- | --- | --- | --- |
| Quick | Step 0 (FI), A1, A3, A6, reduced F, B1 (2 configs), B2, B3, B4, C1; D5 optional with tripod | 23, or 38 with D5 | 20 to 30 |
| Standard | Quick + A2, A4, A5, A7, B5, B6, B1 full, C2, C3, C4 (if available), D1, D3 to D5, D9, E1, E5, full F | about 85, +12 with C4 | 60 to 90 |
| Full | Standard + D2 to D4 on all points with 5 attempts on two lenses, D6 to D8 where supported, E2 to E4, E6, E7 | about 105 + 10 x N | 3 h or more |

`[Inference]` Example: for a body rated at 200,000 actuations, a Standard session of about 100 shots uses 0.05% of rated life. The plan screen shows this figure when rated life is known.

## 10. Execution order

1. Step 0 and group A (read only).
2. Reduced F (physical blockers). On a Blocker the wizard recommends stopping.
3. Group B.
4. Group C.
5. Group E.
6. Group D.
7. Full F (remaining items), summary and report.
