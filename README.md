# camera-preflight

A Windows desktop wizard that checks a used digital camera before you buy it. It walks you through a short series of shots, analyses the RAW files and writes a self-contained HTML report covering the sensor, the shutter, autofocus, metering and the physical condition of the body.

> **Status: pre-release.** The upload-mode wizard and the connected-mode flow are implemented and tested on synthetic frames and a simulated camera. The Canon, Nikon and Sony SDK adapters are written and tested against fake layers but have not completed a session on a real camera. Every analysis threshold is a `[Guess]` until it is calibrated on real bodies. Package-by-package status: [docs/WORK-PACKAGES.md](docs/WORK-PACKAGES.md) section 10.

## What it checks

| Group | Checks |
| --- | --- |
| A. Identification | Model, firmware and serial; battery; shutter count where readable; storage; mounted lens; reminder to clear previous-owner data |
| B. Sensor | Hot, dead and stuck pixels from dark and flat frames; dust and marks; uniformity; noise and banding |
| C. Shutter | Burst rhythm; curtain uniformity across speeds; exposure repeatability; mechanical versus electronic shutter |
| D. Autofocus | Point map; per-point focus attempts; edge contrast versus the centre point; repeatability; body or lens |
| E. Metering | Consistency; between metering modes; spot position; compensation, ISO and aperture linearity |
| F. Physical | Guided manual checks with optional photos |

Procedures and verdict rules are in [docs/TEST-CATALOGUE.md](docs/TEST-CATALOGUE.md). Known faults of specific models, serial ranges and firmware versions come from a curated, sourced knowledge base in [knowledge-base/](knowledge-base/).

## Two ways to use it

- **Upload mode** (always available). The wizard tells you which shots to take; you take them on the camera and add the RAW files step by step. Each file is checked for the right settings before it is used.
- **Connected mode** (optional). With the camera on USB, the app sets the camera, takes the shots and downloads the files itself, and only asks you to do what it cannot do over USB. It uses standard PTP, or a vendor SDK when one is available (Canon EDSDK, Nikon Remote SDK or D-SLR modules, Sony Camera Remote SDK).

## Principles

- No check reports **Pass** unless it ran on the required accepted frames. Otherwise the result is **Not tested**, with a reason.
- Autofocus and metering findings are reported as **Suspect** with a confidence level, not as a binary verdict.
- No buy or price advice, and no single overall score.
- No network access and no telemetry. Personal metadata (owner name, copyright, GPS and similar) is never stored, logged or reported.
- The interface and the report are available in English and Vietnamese.

## Requirements

- Windows 10 22H2 or Windows 11, 64-bit.
- Running from source: [uv](https://docs.astral.sh/uv/) and Python 3.12 or later. [ExifTool](https://exiftool.org/) on `PATH` for metadata reading; release builds bundle it.
- Release builds are not code-signed. Windows SmartScreen may show "Windows protected your PC"; choose **More info**, then **Run anyway**. Check the download against the published `SHA256SUMS` first.

## Run from source

```bash
uv sync
```

```bash
uv run camera-preflight
```

Other commands:

| Command | What it does |
| --- | --- |
| `uv run camera-preflight demo` | Runs the whole wizard on a simulated camera and writes an HTML report to `demo/` |
| `uv run camera-preflight analyse --check B2,B5 a.dng b.dng c.dng` | Analyses chosen photos for chosen checks (`--check all` for every check) |
| `uv run camera-preflight --self-test` | Runs the built-in synthetic session |
| `uv run camera-preflight gui --lang vi` | Starts the wizard in Vietnamese |

## Vendor SDKs

No vendor SDK file is included in this repository, its source archives or CI builds. The binary release built by the maintainer bundles the SDK runtime files. If you build from a clone, download each SDK from the vendor and put it under `sdk/<brand>/` (see [sdk/README.md](sdk/README.md)), or point the app at its folder in Settings. Without an SDK, the features that need it are reported as Not tested and everything else works.

## Development

```bash
uv run ruff check . && uv run ruff format --check .
```

```bash
uv run pyright && uv run lint-imports
```

```bash
uv run python tools/i18n.py check && uv run python tools/kb.py validate
```

```bash
QT_QPA_PLATFORM=offscreen uv run pytest
```

Contributors and coding agents start with [AGENTS.md](AGENTS.md) and [CONTRIBUTING.md](CONTRIBUTING.md). Hardware results go into [docs/hardware-log/](docs/hardware-log/).

## Documentation

| Document | Content |
| --- | --- |
| [docs/DECISIONS.md](docs/DECISIONS.md) | Decision register (confirmed, proposed, open) |
| [docs/SRS.md](docs/SRS.md) | Software requirements specification |
| [docs/TEST-CATALOGUE.md](docs/TEST-CATALOGUE.md) | Check procedures, analysis and verdict rules (groups A to F) |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Technology, layers and project structure |
| [docs/UX.md](docs/UX.md) | Screens, interaction and copy rules, vocabulary |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Releases, milestones, exit criteria |
| [docs/WORK-PACKAGES.md](docs/WORK-PACKAGES.md) | Work packages and implementation status |
| [docs/VERIFICATION.md](docs/VERIFICATION.md) | Open verification tasks |
| [docs/LICENSING.md](docs/LICENSING.md) | Licensing and legal constraints |
| [docs/REFERENCE-IMAGES.md](docs/REFERENCE-IMAGES.md) | Reference photo candidates and licence status |
| [docs/DESIGN-REVIEW.md](docs/DESIGN-REVIEW.md), [docs/archive/handoff.md](docs/archive/handoff.md) | Historical design review and original handoff |

## Trademarks

Brand and model names are used only to describe compatibility. They are trademarks of their respective owners.

## License

Apache-2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
