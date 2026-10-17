# Open Verification Tasks

Facts the design depends on but which are not yet verified. V-01 to V-12 come from the handoff (H§12); V-13 onward come from the design review. Kept here, not as GitHub issues, by maintainer decision (2026-10-16).

Status values: Open, In progress, Closed (with result and date), Dropped (with reason).

| ID | Question | Why it matters | Method | Needed by | Status |
| --- | --- | --- | --- | --- | --- |
| V-01 | Do Canon, Nikon and Sony SDK terms allow open-source adapters (bindings, headers, wrappers) in a public repo? | R-11, FR-CON-06 | Read full terms per vendor and region | M6 | Open |
| V-02 | Apply for Canon SDK (2 to 4 weeks `[Sourced]`) and Sony SDK; which Canon entity covers a Vietnam-based applicant? | SDK adapters | Application | M6 | Open |
| V-03 | Can EDSDK or Nikon SDK set optical-viewfinder AF points and report per-point focus confirmation? | D2 tethered, D6 | API reference reading | M5 | Open |
| V-04 | PTP on real Nikon and Sony bodies: device info, serial, capture | M6 backends | Hardware test | M6 | Open |
| V-05 | How to read the shutter count on Canon bodies newer than DIGIC 5 | A3 | Hardware test, community sources | M4 | Open |
| V-06 | Which Nikon and Sony models have reliable AF metadata decoders? | Gate G6, FR-KB-05 | ExifTool output on sample frames per model | M5 | Open |
| V-07 | Calibrate B, C, D, E thresholds with synthetic defects and real cameras | NFR-02, all `[Guess]` thresholds | Synthetic suite plus real-body data | v0.2 (B, C), v0.4 (D, E) | Open |
| V-08 | Priority model list for KB v1 | M3 seed, M5 KB v1 | Maintainer decision (O-02) | M3 | Open |
| V-09 | Windows USB driver requirements per brand | FR-CON-05 | Spike S-USB | M4 | Open |
| V-10 | PTP over USB from Python on Windows: viable, or .NET helper? | M4 transport | Spike S-USB | M4 | Open |
| V-11 | Licences of all shipped dependencies; prepare NOTICE | NFR-13 | Read licence files of exact versions | v0.1 | Open |
| V-12 | Code signing for Windows releases | SmartScreen prompt | Decision O-03 | v0.1 or later | Open |
| V-13 | Does WPD pass vendor PTP operations (e.g. Canon 0xD1AC, capture) through its MTP extension commands for cameras? | R-03, avoid driver replacement | Spike S-USB step 1 | M4 | Open |
| V-14 | Which LibRaw version ships in the current rawpy wheels, and does it decode CR3, recent NEF and ARW of priority models? Does it read vendor-converted DNG? | AS-01, FR-META-03 | Decode sample files | M1 | Open |
| V-15 | Under AF-S with focus priority, does each brand refuse to release the shutter without focus, and how does a tethered capture report it (error code, timeout)? | R-01, FR-TST-06 | Hardware test per brand, SDK and PTP docs | M3 | Open |
| V-16 | ExifTool licence and terms for bundling the Windows executable; which maker-note fields are needed and available per brand | AS-02, NFR-13 | Read licence; sample outputs | M1 | Open |
| V-17 | Which bodies write sub-second capture timestamps usable for C1? | C1 accuracy | Sample frames per model | M1 | Open |
| V-18 | Precision of microphone onset detection for shutter intervals in a normal room | N-05 | Prototype with recorded bursts | M6 | Open |
| V-19 | Licences of sample RAW files used in CI (e.g. from public RAW sample collections) | Integration tests | Read per-file licence | M1 | Open |
| V-20 | Which models expose sensor or camera temperature in metadata, and under which tag? | R-15, FR-META-05 | ExifTool output on samples | M3 | Open |
| V-21 | Does Qt ship Vietnamese translations for its standard dialogs? | N-08 | Check PySide6 translations folder | M2 | Open |
| V-22 | Which live-view and property signals are readable per backend for helpers H1 to H7 (dark sensor, flat field, chart in view, steady camera, lens ID, focus mode, card)? | FR-ACQ-10, 11 | Spike on real bodies, recorded live view | M3 | Open |
| V-23 | Can the test environment obtain the Canon, Nikon and Sony SDKs automatically (registration, licence acceptance), or only on a local machine? | D-31, SDK adapter tests | Read download terms; try | M3 | Open |
| V-24 | Licence and attribution of each reference photo candidate in REFERENCE-IMAGES.md (blocked: Commons not reachable from this environment) | D-38, NFR-13 | Open file pages; record attribution | M2 | Open |
