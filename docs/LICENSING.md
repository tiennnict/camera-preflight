# Licensing and Legal Constraints

Not legal advice. This document records constraints and open questions; items marked `[Unverified]` must be checked before the release that ships them (V-11).

## 1. Project licence

- Project code: Apache-2.0 (LICENSE in repo root).
- NOTICE file lists third-party components and their licences; release builds include full licence texts in `licenses/`.

## 2. Vendor SDKs

| Vendor | Known terms | Consequence |
| --- | --- | --- |
| Canon | `[Sourced]` (Singapore terms) non-exclusive, non-transferable, revocable; one year from approval; use only in the applicant's country or region; distribution only as part of the developer's software; approval not guaranteed, 2 to 4 weeks. `[Sourced]` Canon Oceania does not supply the SDK to personal users (Oceania only). `[Unverified]` entity for a Vietnam-based applicant | No Canon SDK in repo or releases; adapter outside repo until V-01 |
| Nikon | `[Sourced]` (third-party source) latest public SDK autumn 2024, download site had been under maintenance | Same rule |
| Sony | `[Sourced]` other open-source projects do not include the SDK and require user download; some functions need a licence on the camera | Same rule |

Rules (R-11, CON-03):

1. No vendor SDK binaries, headers, sample code or SDK-derived bindings in the repo or releases until V-01 confirms what is allowed.
2. The app loads user-supplied adapters only inside the backend host process.
3. The UI reminds the user that SDK use is governed by the vendor's terms.

## 3. Dependencies (to be verified for exact shipped versions)

| Component | Use | Declared licence | Distribution note | Status |
| --- | --- | --- | --- | --- |
| PySide6 / Qt | GUI | LGPLv3 (also GPLv3, commercial) `[Sourced]` | onedir keeps libraries replaceable; ship licence and source offer as required | `[Unverified]` details |
| rawpy | RAW decoding | MIT `[Sourced]` | | `[Unverified]` |
| LibRaw (inside rawpy) | RAW decoding | LGPL-2.1 or CDDL; GPL demosaic packs excluded `[Sourced]` | Keep replaceable | `[Unverified]` |
| NumPy | Numerics | BSD-3-Clause `[Unverified]` | Bundled BLAS licence to check | `[Unverified]` |
| SciPy | Analysis | BSD-3-Clause `[Unverified]` | Bundled libraries to check | `[Unverified]` |
| Pillow | Images | MIT-CMU (HPND) `[Unverified]` | Bundled codecs to check | `[Unverified]` |
| pydantic | Models | MIT `[Unverified]` | | `[Unverified]` |
| PyYAML | KB loading | MIT `[Unverified]` | | `[Unverified]` |
| Jinja2, MarkupSafe | Report | BSD-3-Clause `[Unverified]` | | `[Unverified]` |
| Babel | i18n tooling (build time) | BSD-3-Clause `[Unverified]` | Possibly not shipped | `[Unverified]` |
| ExifTool | Metadata | "Same terms as Perl" (Artistic or GPL) `[Unverified]` | Bundling the Windows executable vs user-supplied: V-16 | `[Unverified]` |
| PyInstaller | Packaging | GPL with bootloader exception `[Unverified]` | Exception intended to allow non-GPL apps `[Unverified]` | `[Unverified]` |
| comtypes | WPD (if chosen) | MIT `[Unverified]` | | `[Unverified]` |
| sounddevice / PortAudio | Audio (later) | MIT `[Unverified]` | | `[Unverified]` |

`[Inference]` Apache-2.0 for the app is compatible with using LGPL libraries as separately replaceable libraries, provided their licence texts and attributions are shipped (H§10).

## 4. Trademarks

- No brand names in the product name (CON-06).
- Brand and model names may appear descriptively (for example "supports Canon EOS bodies") with a trademark notice in README.
- Do not use vendor logos.

## 5. Personal data

- The app does not read owner name, copyright, Wi-Fi or similar settings from the camera (CON-05).
- Only files inside the session's import window, or files the user explicitly selects, are imported (FR-ACQ-02).
- Stored metadata passes an allowlist; personal fields (artist, copyright, owner name, GPS, user comments, network settings) are dropped (FR-META-02).
- Original frame files are kept unmodified for re-verification and may still contain such fields as written by the camera; session export lets the user leave original frames out (FR-SES-07).
- Sessions are stored locally; nothing is transmitted (NFR-06).
- Reports include the camera serial; the UI notes this before sharing a report.

## 6. Sample data in tests

RAW samples used in CI must have a recorded source and licence (V-19) and are downloaded to a cache, not committed.
