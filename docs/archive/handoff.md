# camera-preflight: Project Handoff

Handoff of a design session (originally in Vietnamese) to Claude Code. The repo language is English (code, docs, issues). Repo name: `camera-preflight` (chosen by the maintainer, see section 14). Application type: GUI desktop app distributed as prebuilt releases.

## 0. How to use this file

- Treat this file as the project brief and design baseline. Read sections 1, 2 and 5 first.
- Evidence labels used throughout:
  - `[Sourced]` backed by a document found during research (list in section 15). Snippets from search results only; full pages were not opened.
  - `[Inference]` design reasoning by the assistant, not tested.
  - `[Guess]` a number or threshold with no basis yet.
  - `[Unverified]` needs a real camera or SDK documentation to confirm.
- Nothing in this design has been run on a real camera. Do not present `[Inference]`, `[Guess]` or `[Unverified]` items as facts in code comments, docs or reports.

## 1. Goal and scope

A desktop wizard that helps an individual buyer evaluate a used digital camera before buying.

- Platforms: cross-platform in principle, minimum target is a PC (Windows first).
- Brands: Canon and Nikon required; Sony optional. Support as many camera models as possible.
- Connection: USB. Vendor SDK is optional; standard protocol and file import must also work.
- Wizard is semi-automatic: it guides setup (shooting dark and bright frames, AF chart, etc.), captures or imports images, analyses them, and reports issues.
- Automate as much as possible. Where automation is not possible, fall back to a guided manual step, and record in the report that the step was manual.
- Personal, open-source project.

## 2. Decisions confirmed by the maintainer

1. Personal project, open source.
2. Target user: individual buying a used camera.
3. Accepts "accurate result" as the bar, including reporting AF and metering as "suspect with confidence level" rather than pass/fail.
4. Accepts reporting AF at two tiers: points that never report focus, and points that report focus but are soft or off; for mirrorless Sony, per-region sharpness map instead of per-point lists.
5. Maximum camera model coverage in the knowledge base.
6. Manual guidance is the fallback for anything not automatable.
7. Project language is English.

8. The product is a GUI desktop application shipped as prebuilt release builds, not only a library or CLI.
9. Stack: Python with a PySide6 GUI (recommended in a follow-up session; see section 13). Connection backends stay behind an interface, so one can be replaced by a .NET helper process if Python USB access proves unreliable.

Open decisions: priority model list for the first knowledge-base release, whether Sony is in the first release, code signing of Windows builds.

## 3. Prior art and overlap

- `[Sourced]` ShutterCount (by DIRE Studio, the Mac app; a Windows-capable version was not verified) reads the Canon shutter count over USB or Wi-Fi, and Nikon/Pentax counts from image files. It also logs history, forecasts, warns about outdated Canon firmware and syncs Canon clock.
- `[Sourced]` Web tools read shutter count from the EXIF of an uploaded unedited photo. Nikon and Sony usually write it to EXIF; most Canon bodies do not.
- `[Sourced]` `openshuttercounter` (Go) reads the shutter count on Linux, macOS and Windows without a vendor SDK; its Windows backend was implemented but not yet run against a camera.
- `[Sourced]` gPhoto2/libgphoto2 is a vendor-neutral camera library for Unix-like systems; it supports many cameras for transfer, capture and configuration. Windows use is awkward (MSYS2 or WSL).
- `[Sourced]` Tethering tools built on the Nikon SDK exist (digiCamControl, Nikon Camera Control, others).
- `[Sourced]` Online dead pixel testers exist (upload a dark frame).
- `[Unverified]` No tool was found that combines an active test wizard (capture, read files, read camera data), image analysis and an issue report. The search was limited (US-only, English), so this is not proof that none exists.
- Name collisions found while searching names: archived Microsoft `photo-inspector` (unrelated, different purpose) and `image-provenance-inspector` (unrelated). Existing product name to avoid: ShutterCount.

## 4. What is possible per brand

Terms: **No SDK** = standard PTP/MTP plus community-reverse-engineered vendor extensions, or file import. **SDK** = vendor SDK.

### Common baseline (standard PTP)

- `[Sourced]` PTP defines: get device info, open/close session, storage IDs and info, object handles and info, get object, get thumbnail, delete object, initiate capture, get/set device property.
- `[Sourced]` The `darkgrade` library (TypeScript) implements ISO 15740 and auto-detects Sony, Nikon and Canon vendor extensions: get/set properties, ISO, shutter speed and capture for all four paths; live view for Sony and Nikon, partial for Canon; Sony alpha live view, video, SDIO; Nikon Z live view and extended properties.
- `[Inference]` Retrieval of RAW files via PTP (`GetObject`) is enough for all image analysis.

### Canon

- No SDK: `[Sourced]` FC.SDK (MIT, C#) controls Canon EOS bodies via PTP over USB or Wi-Fi without EDSDK: model, serial, battery, capture, bulb, live view. Tested on EOS 6D only. USB uses LibUsbDotNet (WinUSB on Windows).
- No SDK, shutter count: `[Sourced]` up to roughly the DIGIC 5 generation Canon exposes the counter as PTP property 0xD1AC; newer bodies need another method. `[Unverified]` which method for newer bodies.
- SDK (EDSDK): `[Sourced]` free; USB on Windows, macOS, Linux; remote shooting; live view with AF position, AF result, histogram; transfer, thumbnails, deletion; shooting parameters; setting AF position from live view. `[Sourced]` Cannot talk to several cameras at once.
- `[Sourced]` Metadata: Canon writes number of AF points, AF points in focus, AF points selected into the image (example: EOS M6 Mark II lists 143 points).
- `[Inference]` EDSDK mostly adds stability and coverage of newer bodies, not new diagnostic capability.

### Nikon

- No SDK: `[Sourced]` libgphoto2 supports many Nikon bodies; darkgrade has Nikon Z extensions. Nikon DSLR support via standard PTP detail is `[Unverified]`.
- SDK: `[Sourced]` the C# wrapper docs show capability enumeration per body (`GetCapabilityInfo`), capture with an image-ready event, and JPEG live view frames.
- Risk: `[Sourced]` (third-party source) the latest public Nikon SDK dates from autumn 2024, the download site had been under maintenance, and macOS 15 was not officially supported. Not confirmed with Nikon.
- `[Sourced]` Metadata AF info (AFInfo2) is decoded inconsistently across models (D850, D7500) and absent or identical across images on Z6 III per ExifTool forum reports.

### Sony

- No SDK: `[Sourced]` Sony bodies have USB modes Mass Storage, MTP and Remote Shooting; capture control needs Remote Shooting mode. `[Sourced]` Sony publishes "Camera Remote Command", a PTP command reference for many ILCE bodies, independent of OS.
- SDK: `[Sourced]` Camera Remote SDK (USB; Windows, macOS, Linux) supports settings, shutter release, live view and image transfer. One community project (Sony A7C) selects AF point by live-view click, changes AF area mode, half-presses S1 and reads focus indication. A Python binding gates exposure on confirmed focus. Absolute focus position setting exists; `[Sourced]` its values are not compatible across camera firmware updates. `[Sourced]` Some functions need a licence installed on the camera.
- Shutter count: `[Sourced]` usually in EXIF.
- Metadata AF info: `[Sourced]` AFPointsUsed only for SLT models or ILCE with A-mount lenses; FocusLocation on a7 IV reported with unclear meaning and identical values across shots.

### Internal logs

`[Unverified]` No source shows that any of the three brands exposes an internal error or service log via PTP or SDK. The design does not rely on one.

## 5. Architecture

Six layers, only the connection layer differs per brand:

1. **Camera** (Canon, Nikon, Sony via USB).
2. **Connection backends** (three, interchangeable): (a) standard PTP plus vendor extensions; (b) vendor SDK, optional, user-installed; (c) file import (user shoots by hand, then loads images).
3. **Acquisition**: set up, capture, fetch RAW files, read properties.
4. **Data**: metadata and properties (ExifTool or LibRaw; both decode maker notes including AF info).
5. **Analysis**: test groups A to F.
6. **Verdict**: scoring with confidence, report.

Plus a **knowledge base** (per model data and known defects) feeding analysis and verdict.

Design principles:

1. Four execution paths per test: automatic without SDK, automatic with SDK, semi-automatic (user acts, app reads result from the image), file import.
2. Four result levels: Pass, Suspect, Fail, Not tested, each with confidence. Never report Pass for a test that did not run.
3. AF and metering: Suspect with confidence, not binary.
4. Prefer relative comparisons (versus centre point, between frames of the same camera) over absolute thresholds.
5. Each test declares a maximum number of shots; the report shows shutter count before and after if readable.
6. Raw images and readable properties are stored with the report for re-verification.
7. If automation is impossible, switch to guided manual mode and say so in the report.

## 6. Test scenario

### Preparation

Equipment:

| Item | Used for | Note |
| --- | --- | --- |
| Good USB cable, full battery or external power | Everything | `[Guess]` weak battery or cable can drop the session |
| Known-good memory card | Burst, file fetch | Separate card to avoid mixing with previous owner's images |
| Flat grey or white target, even continuous light | B, C, E | `[Inference]` avoid LED or fluorescent light: causes stripes at fast shutter speeds |
| Body cap | B (dark frames) | |
| AF chart generated by the app, tripod, level | D | Chart generated from the model's AF point layout |
| At least two lenses, one as reference | D, E | `[Sourced]` separates body faults from lens faults |
| Windows PC, suitable USB driver | Connection | `[Unverified]` driver details per brand |

Step 0 (initial survey):

1. Detect camera over USB, identify brand and model, look up the knowledge base (live view, AF type, number of AF points, shutter type).
2. Choose backend: vendor SDK if available, else PTP plus extension, else file import.
3. Prompt for the right USB mode: `[Sourced]` Sony needs Remote Shooting; `[Sourced]` Canon built-in Wi-Fi must be off when using USB.
4. Record current settings: ISO, image quality, noise reduction, AF fine-tune if readable (`[Sourced]` Nikon metadata has this field).
5. `[Inference]` Set capture conditions: RAW, long-exposure and high-ISO noise reduction off, automatic corrections such as vignette compensation off.
6. Shoot one test frame and verify RAW and metadata are readable; if not, demote capture tests to file import.

### Group A: identification and camera data

| Test | Action | Verdict | Path |
| --- | --- | --- | --- |
| A1 Identification and session | Get device info, open session; read model, firmware, serial | User enters the serial printed on the body; mismatch or unreadable = Suspect | No SDK: Canon `[Sourced]`, Nikon and Sony `[Unverified]`; SDK |
| A2 Battery | Read battery level | Record only; battery wear is not directly measurable; ask user to time it manually | No SDK: Canon `[Sourced]`; SDK |
| A3 Shutter count | Canon: PTP 0xD1AC up to ~DIGIC 5; newer: SDK or other `[Unverified]`. Nikon, Sony: EXIF of a frame just shot | Percentage of rated shutter life from knowledge base; report "unreadable", never 0 | No SDK; file import |
| A4 Firmware | Read version | Compare to latest in knowledge base; older = warning | No SDK; SDK |
| A5 Storage | List cards, capacity, file count | Card not recognised or slot fault = Suspect; test each slot | No SDK |
| A6 Mounted lens | Read lens info from metadata of a test frame | Record; becomes the reference lens for group D | File import; SDK |
| A7 Previous owner traces | Guide user through menus: owner name, copyright, saved Wi-Fi | Remind to clear; the app does not read personal data | Manual |

### Group B: sensor

RAW analysis is brand independent. Only capture needs a connection.

| Test | Setup and capture | Analysis | Verdict |
| --- | --- | --- | --- |
| B1 Dark frame | Body cap on; ISO base, 1600, 6400; short and long exposures (bulb where available); long-exposure NR off; at least 3 frames per configuration | Abnormally bright pixels versus neighbours; hot pixel = repeats at same coordinates in at least 2 of 3 frames | Report count, coordinates, colour channel. `[Guess]` cluster of adjacent pixels = Fail; a few isolated = Suspect; none = Pass with note that firmware may have masked pixels `[Inference]` |
| B2 Flat bright frame | Grey or white target, defocused; histogram 50 to 80 percent, no clipping; f/8 to f/11; 3 frames, target shifted slightly | Pixels deviating strongly from neighbours at same coordinates after shifting | Stuck dark or stuck bright pixels; same scale as B1 |
| B3 Pixel classification | Use B1 and B2 | Classify: dead (always dark), stuck bright, hot (bright in long exposure), channel offset | `[Inference]` Bayer sensors have no pure red pixel; report per R, G, B channel with coordinates |
| B4 Dust and marks | Flat frame at f/16 to f/22, strongly defocused; 3 frames; rotate lens on mount between frames | High-pass filter, blob detection. `[Inference]` marks fixed to the sensor = sensor dust; marks that move with the lens = lens dust | Count, size, region. Linear marks may indicate a sensor scratch `[Sourced]`: rate as strongly Suspect |
| B5 Sensor uniformity | Flat frame, base ISO, f/8 or smaller | Brightness grid; look for stripes, boundaries, colour casts; check left-right vignette symmetry (asymmetric vignetting is a warning sign `[Sourced]`) | Anomaly = Suspect with heat map |
| B6 Noise and banding | Dark frames at several ISOs | Standard deviation per channel and ISO; look for horizontal or vertical banding | `[Inference]` no absolute threshold; compare to model reference data if present, else only report banding |

`[Inference]` Accept a frame only if its histogram is in range, not clipped and not flickering; otherwise reject and re-shoot.

### Group C: shutter

Shutter speed accuracy cannot be measured without a reference instrument. Up to about 44 frames for the group.

| Test | Action | Analysis | Verdict |
| --- | --- | --- | --- |
| C1 Burst rhythm | 10 frames at highest burst speed | Intervals between frames (sub-second EXIF timestamps if available) versus rated speed from knowledge base | Large variation or slowdown = Suspect; listen for odd noises (buyer checklists recommend burst testing `[Sourced]`) |
| C2 Uniformity along curtain travel | Flat frames at 1/250, 1/1000, 1/4000, fastest speed; continuous light; 3 frames each | Mean brightness per column and per row; gradient along travel | `[Inference]` significant gradient = uneven curtain. Regular stripes are light flicker, not counted; compare frames to tell |
| C3 Repeatability | 10 identical frames, flat scene | Brightness spread between frames in EV | `[Guess]` spread over 0.1 EV = Suspect |
| C4 Mechanical vs electronic | If the body has electronic or EFCS mode, repeat C2 in both | Compare modes | `[Inference]` fault only in mechanical = suspect curtain; fault in both = suspect sensor or lighting |
| C5 Absolute speed | Not measured | Needs reference | Report Not tested |
| C6 Sound and mirror | Guided listening | Mirror smooth, shutter not sticking | Manual, see group F |

### Group D: autofocus

Two tiers: (1) selected point never reports focus; (2) point reports focus but is soft or off. All conclusions are Suspect with confidence. Maximum shots = AF points x repeats x lenses.

Protocol (D0):

- Chart: app-generated high-contrast grid covering the area of each AF point, perpendicular to the camera, tripod, adequate non-flickering light.
- Use AF-S with focus priority, a single AF point, AF area expansion off `[Sourced]`.
- Before every shot, rack the focus away so the camera must refocus from scratch; AF-S phase detect may not refocus if the current reading is acceptable `[Sourced]`.
- DSLR: shoot through the optical viewfinder path (mirror down), not Live View, because Live View uses contrast AF rather than the phase detect sensor `[Sourced]`.
- Fix a reference lens for the session; record AF fine-tune if readable.

| Test | Action | Analysis and verdict | Path |
| --- | --- | --- | --- |
| D1 AF point map | Look up point count, type (cross or line), layout in the knowledge base; if the model is unknown, read point count and selected points from metadata | Drives chart generation and the list of points to run | Knowledge base; Canon metadata `[Sourced]` |
| D2 Points that never report focus (tier 1) | Select each point; 3 shots (standard) or 5 (full), refocus between | Selected point absent from the in-focus list in at least 2 of 3 shots = Suspect. Canon high confidence; Nikon only for models with a verified decoder; skip tier 1 for Sony mirrorless `[Sourced]` | Point selection: manual joystick for DSLR; Sony via SDK `[Sourced]`; Canon and Nikon via SDK `[Unverified]` |
| D3 Points in focus but soft (tier 2) | Reuse D2 shots | Sharpness (edge contrast) around each point versus centre point in the same session; difference to centre is more stable than absolute values `[Sourced]`. Prioritise left and right edge points, because users report left-side AF misalignment on some bodies `[Sourced]` | Image analysis, all brands |
| D4 Repeatability | Reuse D2 and D3 data | `[Inference]` large spread of sharpness across repeats of one point = unstable AF = Suspect | Image analysis |
| D5 Reduced sample (quick level) | Centre plus four outermost points (top, bottom, left, right) | Run D2 to D4 on 5 points; this sampling follows a commercial AF test tool `[Sourced]` | As D2 |
| D6 Mirrorless by region | Divide frame into a grid sized to the chart resolution; per region: AF, shoot, measure sharpness | Sharpness heat map by region; no concept of a broken point | Sony: click AF point on live view, change area mode, half-press S1, read focus indication `[Sourced]`; Canon: EDSDK sets AF position from live view `[Sourced]`; Nikon `[Unverified]` |
| D7 AF response time | Time from half-press to focus confirmation, where the SDK exposes the event | `[Inference]` unusually long time versus model reference = Suspect | Sony has focus feedback `[Sourced]`; others `[Unverified]` |
| D8 Absolute focus position | Drive to a preset position and read back | Not reaching or offset = Suspect lens or body | Sony SDK `[Sourced]`; re-measure after firmware updates `[Sourced]` |
| D9 AF fine-tune | Read value if present in metadata | `[Inference]` if enabled and non-zero, warn and recommend repeating D3 with it off | Nikon metadata `[Sourced]`; others `[Unverified]` |
| D10 Body or lens | Repeat D2 and D3 with a second lens | Fault with one lens only = lens; fault with both = body `[Sourced]` | As D2 |

AF verdict rules:

- Fail only when the fault repeats over multiple shots and with both lenses.
- A few mildly off points are normal in commercial AF test tools `[Sourced]`: rate as mild Suspect, not Fail.
- `[Inference]` The centre point (cross type) is usually the most accurate, so a fault there has higher severity.
- Report as an AF point map coloured by the four result levels.

### Group E: metering and exposure

Consistency and linearity only; absolute metering accuracy is not feasible without a reference. Up to about 30 frames.

| Test | Action | Analysis | Verdict |
| --- | --- | --- | --- |
| E1 Consistency | Even grey scene; P or Av; fixed ISO; 5 frames | Read shutter, aperture, ISO chosen by the camera from EXIF | `[Guess]` spread over 1/3 EV = Suspect |
| E2 Between metering modes | Same scene; evaluative, centre-weighted, spot | Compare resulting exposures | `[Inference]` on a uniform scene all modes should agree; large deviation = Suspect |
| E3 Spot position | Chart with bright and dark regions; move bright region off centre; spot metering | Exposure must follow the measured region | `[Inference]` no change = Suspect spot metering |
| E4 Output level | Grey scene, auto exposure | Mean RAW grey level versus nominal mid-grey | `[Inference]` systematic offset can be by design; compare only to model data or between two lenses; do not call a fault from one body |
| E5 Compensation linearity | Exposure compensation ladder -2 to +2 EV, 5 frames | Output brightness should step evenly | `[Inference]` clear nonlinearity = Suspect |
| E6 ISO linearity | Fixed shutter and aperture, step ISO | RAW brightness after black level subtraction should rise per ISO step | `[Inference]` abnormal jumps = Suspect |
| E7 Aperture steps | Fixed shutter and ISO, close aperture stepwise | Brightness should fall evenly | `[Inference]` abnormal step = suspect aperture blades or lens; cross-check with D10 |

### Group F: physical and manual functions (guided checklist)

The wizard shows each item; the user marks Pass, Suspect or Fail with notes and optional photo.

- Body and structure: cracks, dents, corrosion, scratched screws (signs of opening); lens mount play and wear, contacts; battery door, card slot, ports, port covers; tripod socket, hot shoe, dials and rings.
- Controls: every button, dial, joystick, lever, power switch (list per model from knowledge base); touchscreen across the full surface if present.
- Displays and finder: LCD and EVF using app-exported solid colour images (red, green, blue, white, black) played back to find dead pixels, marks, colour casts; optical viewfinder dust and diopter.
- Mirror and shutter (DSLR): smooth mirror motion, quiet burst, no odd noise.
- Flash and sync: pop-up flash fires, hot shoe accepts external flash, shoot at rated sync speed and check for black bands.
- Power, connectivity, video: battery holds charge and charger works; HDMI, mic, headphone, USB ports; Wi-Fi and Bluetooth enable; 10 second video with audio that opens.
- Bundled lens: scratches, dust, internal fungus; smooth focusing without grit `[Sourced]`; aperture and zoom rings smooth; stabilisation works.

`[Inference]` The solid-colour image set, item order and result recording are design proposals.

## 7. Capability matrix

KS = no SDK (standard PTP, community vendor extension, file import). SDK = vendor SDK.

| Function | Canon | Nikon | Sony |
| --- | --- | --- | --- |
| Connection, camera info | KS: yes, incl. model, serial, battery `[Sourced]`. SDK: yes | KS: standard PTP device info `[Sourced]`; serial `[Unverified]`. SDK: capability query per body `[Sourced]` | KS: Remote Shooting mode or Camera Remote Command `[Sourced]`. SDK: yes |
| Capture from PC | KS: yes, FC.SDK tested on 6D only `[Sourced]`. SDK: EDSDK `[Sourced]` | KS: Nikon Z extension `[Sourced]`; libgphoto2 covers many models, per model `[Unverified]`. SDK: yes `[Sourced]` | KS: needs Remote mode or Remote Command `[Sourced]`. SDK: yes `[Sourced]` |
| Fetch RAW | KS: yes (standard PTP) `[Sourced]` | KS: yes | KS: yes |
| Set ISO, shutter, aperture | KS and SDK: yes `[Sourced]` | KS and SDK: yes `[Sourced]` | KS and SDK: yes `[Sourced]` |
| Live view | KS: partial `[Sourced]`. SDK: yes with AF position, result, histogram `[Sourced]` | KS: Nikon Z `[Sourced]`. SDK: JPEG frames `[Sourced]` | KS: yes `[Sourced]`. SDK: yes `[Sourced]` |
| Bulb | KS: yes `[Sourced]` | `[Unverified]` | `[Unverified]` |
| Shutter count | KS: PTP to ~DIGIC 5 `[Sourced]`; newer `[Unverified]` | EXIF `[Sourced]` | EXIF `[Sourced]` |
| AF data in image | Good `[Sourced]` | Partial, model dependent `[Sourced]` | Limited `[Sourced]` |
| Set AF point or area from PC | SDK: via live view `[Sourced]`; optical AF `[Unverified]` | `[Unverified]` | SDK: click on live view, change area mode `[Sourced]` |
| Focus confirmation feedback | SDK: AF result in live view `[Sourced]` | `[Unverified]` | SDK: focus indication on half press `[Sourced]` |
| Absolute focus position | `[Unverified]` | `[Unverified]` | SDK: yes `[Sourced]` |
| Notable limits | EDSDK single camera at a time; licence one year, per country `[Sourced]` | Public SDK latest from autumn 2024, download site had been under maintenance (third-party source) `[Sourced]` | Some functions need a licence on the camera `[Sourced]` |

Internal error log: `[Unverified]`, not relied upon.

## 8. Run levels and order

Order of execution (increasing shooting cost, stop early on a blocker):

1. Step 0 and group A (read only).
2. Reduced group F (physical blockers: no power, stuck mirror, obviously scratched sensor).
3. Group B.
4. Group C.
5. Group E.
6. Group D (most frames, last).
7. Summary and report.

`[Inference]` On a Blocker at steps 1 or 2, the wizard suggests stopping and lets the user decide.

| Level | When | Content | Max shots (estimate) |
| --- | --- | --- | --- |
| Quick | On-site inspection, little time | Step 0, A1, A3, reduced F, B1 one config, B2, B4, C3, D5 (5 points, 3 repeats) | ~35 |
| Standard | Longer trial or just received | All A, B, C1 to C4, E1 to E5, full F; D2 to D4 on all AF points, one lens, 3 repeats | ~80 + 3 x AF points |
| Full | Return policy or high-value body | All tests; D with 5 repeats on two lenses plus D6 to D10 | ~95 + 10 x AF points |

`[Inference]` Example for a hypothetical 61-point body: Standard ~263, Full ~705 shots. Each shot adds to the shutter count, so the wizard shows the planned shot count before running and lets the user skip tests.

## 9. Reporting, severity, knowledge base

Report contents:

- Summary: counts of Pass, Suspect, Fail, Not tested; Blocker items listed separately.
- Camera info: brand, model, serial, firmware, shutter count before and after the session, lens used.
- Results table per group A to F with confidence and path used (automatic, semi-automatic, file import, manual).
- Evidence: defect pixel map, dust map, coloured AF point map, stability charts, attached raw images.
- Not tested list with reasons (no SDK, model limitation, user skipped).
- Suggested actions: ask the seller about suspect items, further checks, or warranty. The report gives no price advice and no buy decision.

Severity levels (`[Inference]`; no single aggregate score, because an average hides serious faults):

| Level | Examples | Shown |
| --- | --- | --- |
| Blocker | No power; clearly scratched sensor; stuck mirror; centre AF point fault repeating on two lenses | Top of report |
| High | Cluster of defective pixels; uneven shutter; many AF points never report focus | Top of each group |
| Medium | A few hot pixels; heavy sensor dust | In group table |
| Low | Mildly off edge AF points; cosmetic wear | In group table |

Knowledge base: versioned YAML files in the repo, each entry with a source and a confirming test.

```yaml
model: <brand and model name>
release_year: <year>
shutter_type: <mechanical | electronic | both>
rated_shutter_life: <count, with source>
af:
  point_count: <number>
  point_type: <cross | line | region>
  layout: <normalised coordinates per point>
  metadata_decoder: <verified | unverified>
firmware:
  latest: <version, date>
backend:
  no_sdk: <canon_ptp | nikon_ext | sony_remote | libgphoto2 | none>
  sdk: <yes | no>
known_issues:
  - id: <id>
    description: <symptom>
    scope: <firmware or serial range>
    confirming_test: <test id, e.g. D2>
    confidence: <high | medium | low>
    source: <link>
```

Rules:

- A known issue raises priority of related tests and shows a warning; it never concludes the camera is faulty by itself.
- Entries without an official source get low confidence.
- If `metadata_decoder` is unverified for a model, skip tier 1 of D2, because Nikon and Sony AF metadata decoding is inconsistent across models `[Sourced]`.
- Contributions by pull request; each entry requires a source and a confirming test.
- `[Unverified]` Content sources (manufacturer service notices and recalls, technical forums) have not been surveyed. The first release needs a priority model list.

## 10. Licensing and legal constraints

- `[Sourced]` Canon SDK licence (Singapore terms): non-exclusive, non-transferable, revocable; valid one year from approval; for use only in the country or region of the application; the SDK may be distributed only as part of the developer software. Approval is not guaranteed and typically takes 2 to 4 weeks. `[Sourced]` Canon Oceania states it does not supply the SDK to personal users (Oceania only; applies to Australia and New Zealand developers). `[Unverified]` Which Canon entity covers a Vietnam-based applicant.
- `[Unverified]` Whether the vendor SDK licences allow a public open-source repo to distribute the SDK. Assumption for design: do not bundle any SDK in the repo. The user downloads the SDK from the vendor and points the app to it.
- `[Sourced]` Sony Camera Remote SDK: other open-source projects state they do not include the SDK and require the user to download it.
- Do not use brand names in the project name (trademark risk, `[Inference]`).
- Do not read or store previous-owner personal data from the camera.
- Dependency licences: `[Sourced]` PySide6 is LGPLv3 (also GPLv3 or commercial). `[Sourced]` rawpy is MIT and builds on LibRaw under LGPL-2.1; the GPL demosaic packs are excluded. `[Inference]` Apache-2.0 for the app is compatible with using these as separate libraries, provided the LGPL texts and attributions are shipped (a NOTICE file) and the libraries stay replaceable (folder distribution, section 13). `[Unverified]` Licences of OpenCV, ExifTool and other dependencies have not been checked. The maintainer must review licences before the first release.

## 11. Risks and counterarguments

| Risk | Mitigation |
| --- | --- |
| Many shots raise the shutter count | Show planned shots first; three levels; allow skipping tests |
| Lens or chart noise in AF results | Two lenses; compare to centre; Suspect before Fail |
| Firmware masks defective pixels | Report Pass with a note that pixels may be masked |
| Flicker or wrong shooting conditions | Check histogram and flicker; reject and re-shoot |
| AF metadata decoded wrongly for some models | Verified-decoder flag in knowledge base |
| SDK licence restrictions | Do not bundle SDK; user supplies it; read each vendor's terms |
| User picks the wrong AF point manually | Compare selected point in metadata before accepting a frame `[Inference]` |
| Thresholds in B, C, E have no empirical basis | Calibrate with synthetic defects injected into real images, and real cameras |

Strongest counterargument `[Inference]`: a buyer inspecting in person has only minutes, so the most valuable release may be the Quick level (groups A, B and reduced F). Full group D is realistic only with a return policy. Design all three levels, ship Quick first.

## 12. Open verification tasks

1. Read SDK terms of Canon, Nikon and Sony about distribution in an open-source project.
2. Apply for the Canon SDK (typically 2 to 4 weeks) and the Sony SDK.
3. Read EDSDK and Nikon SDK API references: can optical AF points be set from the PC, and is per-point focus confirmation available?
4. Test PTP on real Nikon and Sony cameras: device info, serial, capture.
5. Test shutter count reading on a newer Canon body.
6. Verify AF metadata decoders per Nikon and Sony model.
7. Calibrate B, C, E thresholds with synthetic defect images and real cameras.
8. Fix the priority model list for the first knowledge-base release.
9. Determine Windows USB driver requirements (WinUSB or alternative) per brand.
10. Spike: PTP over USB from Python on Windows (Canon first). Decide whether the connection backend stays in Python or moves to a .NET helper process.
11. Check licences of all planned dependencies (OpenCV, ExifTool, others) and prepare the NOTICE file.
12. Decide on code signing for Windows releases.

## 13. Suggested repo layout, stack and milestones

Stack decision (follow-up session): **Python 3.12 or newer with a PySide6 GUI**.

Why:

- `[Inference]` The novel value of the product is image analysis, not device control. Python has the strongest ecosystem for it: NumPy, OpenCV, and `rawpy` (a LibRaw wrapper) which already includes hot and dead pixel detection helpers `[Sourced]`.
- `[Sourced]` Vendor SDKs are native C/C++ libraries (Canon EDSDK; Sony SDK, which also has a community Python binding). `[Inference]` Python can load a user-supplied SDK DLL at runtime with `ctypes` or `cffi`, which fits the no-bundled-SDK rule in section 10.
- `[Sourced]` PySide6 is LGPLv3 (also GPLv3 or commercial); PyQt6 is GPLv3 or commercial. Use PySide6, not PyQt6.
- Connection backends stay behind an interface (section 5): ExifTool as a subprocess, SDKs loaded at runtime, file import as the guaranteed fallback.

Alternatives considered `[Inference]`:

| Option | Strength | Weakness |
| --- | --- | --- |
| Python + PySide6 (chosen) | Best analysis ecosystem; fast iteration | USB/PTP access from Python on Windows is less proven than the C# FC.SDK path; large release size |
| C# + Avalonia | `[Sourced]` Avalonia targets Windows, macOS, Linux with single-file publish; FC.SDK and Canon EDSDK .NET wrappers are C# | Weaker image analysis ecosystem; more code for the analysis layer |
| Rust + Tauri or egui | Small binaries; `[Sourced]` a Rust Sony SDK binding exists | Analysis ecosystem and native SDK FFI both cost more |

Fallback: if the M2 spike shows that PTP over USB from Python is unreliable on Windows, keep Python for GUI and analysis and move only the connection backend into a small .NET helper process (for example around FC.SDK) that talks to the app over stdin/stdout JSON. `[Unverified]` The maturity of Python PTP libraries (for example `PTPy`) has not been tested.

Release builds (GUI app with prebuilt releases):

- GitHub Actions builds a release per version tag. Windows first; macOS and Linux later.
- `[Sourced]` PyInstaller `--onefile` output is a self-extracting archive and is frequently reported as flagged by antivirus engines, including Microsoft Defender. The reports come mostly from blogs, a release note and a vendor of a competing packager, so exact rates are `[Unverified]`. Prefer a folder (onedir) build, zipped or wrapped in an installer. `[Sourced]` Nuitka standalone is an alternative that one open-source project adopted after false positives; Nuitka onefile has a similar extraction behaviour.
- `[Sourced]` Unsigned builds trigger the Windows SmartScreen unknown publisher prompt. Code signing is an open decision.
- `[Inference]` A folder build also keeps LGPL libraries (PySide6, LibRaw) replaceable by the user.
- Never include vendor SDK binaries in a release. The app asks the user for the SDK path.
- Build a release in CI from milestone M0 so packaging and antivirus problems surface early.

Suggested layout (`[Inference]`):

```
camera-preflight/
  README.md
  LICENSE               Apache-2.0 (see section 10)
  NOTICE                third-party attributions
  pyproject.toml
  .github/workflows/    CI and release builds
  packaging/            PyInstaller (onedir) or Nuitka config, installer scripts
  docs/
    DESIGN.md           (from sections 5 to 9 of this file)
    TEST-SCENARIO.md    (section 6)
    LICENSING.md        (section 10)
  src/
    backends/           ptp/, vendor_sdk/ (user-supplied), file_import/
    acquisition/
    analysis/           pixels/, dust/, shutter/, af/, metering/
    gui/                PySide6 views
    wizard/             step logic, independent of the GUI
    report/
    knowledge/          schema + loader
  knowledge-base/       YAML per model
  tests/                synthetic-defect fixtures
```

Milestones (`[Inference]`):

1. **M0** File-import mode with a minimal GUI: analysis of dark and flat frames (B1 to B4), report with evidence images. No camera connection needed. CI produces a prebuilt Windows release folder.
2. **M1** Wizard UI with guided manual steps (group F, shooting instructions), Quick level end to end.
3. **M2** One backend with real capture (Canon via PTP, the best documented no-SDK path), groups A to C.
4. **M3** AF tests (D) with metadata decoders and verified-model flags; knowledge base v1.
5. **M4** Nikon, then Sony backends; optional SDK adapters.

## 14. Repo name proposals

Rules applied: English, lowercase kebab-case, no brand names (trademark risk, `[Inference]`), avoid the existing product name ShutterCount `[Sourced]`, avoid "dslr" because mirrorless is in scope.

| Name | Why | Risk |
| --- | --- | --- |
| `usedcam-check` (recommended) | Says exactly what it does; easy to search; CLI can be `usedcam` | `[Unverified]` No collision found in a limited search; not a full GitHub search |
| `camera-preflight` | Pre-purchase "preflight" metaphor | Less descriptive |
| `camera-inspector` | Generic and clear | Generic; similar names exist (`photo-inspector`, archived, unrelated) |
| `shutter-and-focus` | Hints at core tests | Narrower than the full scope |

Chosen by the maintainer: `camera-preflight`. GitHub reported it as available when creating the repository; this does not rule out similar names elsewhere. Initial GitHub settings: public, README on, `.gitignore` template Python, licence Apache-2.0. After creation, add to `.gitignore`: a vendor SDK folder (for example `vendor-sdk/`), RAW files (`*.CR2`, `*.CR3`, `*.NEF`, `*.ARW`), report output, and packaging output (`build/`, `dist/`).

## 15. Sources (from search results; full pages not opened)

- Canon SDK terms (Singapore): https://asia.canon/en/campaign/developerresources/terms-conditions-for-digital-camera-software-development-kit-sdk
- Canon CAP (EDSDK, CCAPI): https://asia.canon/en/campaign/developerresources/cap
- Canon SDK (UK): https://www.canon.co.uk/business/imaging-solutions/sdk/
- Canon Oceania SDK notice: https://www.canon.co.nz/support/support-news/support-news/digital-slr-camera-software-developers-kit
- FC.SDK: https://www.nuget.org/packages/fc.sdk
- darkgrade: https://github.com/darkgrade/darkgrade
- PTP operation codes: https://docs.rs/mtp-rs/0.1.0/mtp_rs/ptp/enum.OperationCode.html
- openshuttercounter: https://pkg.go.dev/github.com/mvisonneau/openshuttercounter
- ShutterCount Pro: https://www.waerfa.com/shuttercount-pro
- Camera Shutter Count Checker: https://pixelpeeper.com/camera-shutter-count
- gPhoto2 overview: https://www.oreilly.com/library/view/opencv-3-blueprints/9781784399757/ch02s02.html
- Nikon SDK C# wrapper FAQ: https://sourceforge.net/p/nikoncswrapper/wiki/Frequently%20Asked%20Questions/
- Nikon SDK status (Pictomic): https://confluence.pictomic.com/x/OAEd
- Third-party software on the Nikon SDK: https://nikonrumors.com/2015/07/08/available-third-party-software-solutions-based-on-the-nikons-sdk.aspx
- Sony Camera Remote Toolkit: https://pro.sony/en_GB/digital-imaging/sdk
- Sony Camera Remote SDK releases: https://support.d-imaging.sony.co.jp/app/sdk/licenseagreement_d/ja.html
- Sony Camera Remote Command: https://support.d-imaging.sony.co.jp/app/cameraremotecommand/ja/index.html
- Sony USB connection modes: https://helpguide.sony.net/ilc/2430/v1/en/contents/0601_usb_connection.html
- TetherMoon (Sony SDK, Rust): https://github.com/SpaceDLFactory/TetherMoon
- crsdkpy (Sony SDK, Python): https://pypi.org/project/crsdkpy/
- ExifTool forum, Nikon AFInfo (D7500): https://exiftool.org/forum/index.php?msg=91265
- ExifTool forum, Nikon Z6 III AFInfo: https://exiftool.org/forum/index.php?msg=90584
- ExifTool Sony tags: https://exiftool.sourceforge.net/TagNames/Sony.html
- ExifTool forum, Sony a7 IV FocusLocation: https://exiftool.org/forum/index.php?msg=77145
- Canon EOS M6 Mark II EXIF sample: https://old.imaging-resource.com/PRODS/canon-eos-m6-ii/EXIF/YIMG_1750.HTM
- LibRaw Nikon makernotes: https://docs.rs/libraw-rs-sys/latest/libraw_sys/struct.libraw_nikon_makernotes_t.html
- Photography Life, AF test: https://photographylife.com/how-to-quickly-test-your-dslr-for-autofocus-issues
- Kasson, D850 AF accuracy: https://blog.kasson.com/?p=21838
- Testing the AF sensor array: https://falklumo.com/lumolabs/articles/D800Focus/SensorArray.html
- dpreview, D7100 left AF: https://www.dpreview.com/forums/post/51122118
- Canon Rumors, 5D III bad AF points: https://www.canonrumors.com/forum/posts/264504/
- Lens Defect Detective (vignette asymmetry): https://www.adorama.com/alc/lens-defect-detective
- Lensrentals, used gear: https://www.lensrentals.com/blog/?p=43788
- Castle Cameras, used camera checks: https://www.castlecameras.co.uk/used-cameras/c137
- Cizucu, used camera checklist: https://www.cizucu.com/news/2025-02-used-camera-checklist
- Imagen AI Dead Pixel Tester: https://imagen-ai.com/tools/dead-pixel-tester/
