# camera-preflight
Open-source wizard that checks a used digital camera before you buy: sensor pixels, dust, shutter, autofocus and metering, with guided manual fallback.

**Status:** pre-release. The upload-mode wizard and the connected-mode flow are implemented and tested on synthetic frames and a simulated camera. Nothing has been tested on a real camera yet, and every threshold is a `[Guess]` to be calibrated. Details: [docs/WORK-PACKAGES.md](docs/WORK-PACKAGES.md) section 10.

## Run from source

```
uv sync
uv run camera-preflight            # graphical wizard
uv run camera-preflight demo       # whole wizard on a synthetic camera, writes an HTML report
uv run camera-preflight analyse --check B2,B5 photo1.dng photo2.dng photo3.dng
uv run camera-preflight --self-test
```

Development checks: `uv run ruff check .`, `uv run pyright`, `uv run lint-imports`, `uv run python tools/i18n.py check`, `QT_QPA_PLATFORM=offscreen uv run pytest`. ExifTool must be installed for the tests that read real metadata; release builds bundle it.

## Requirements

- Windows 10 22H2 or Windows 11, 64-bit.
- Release builds are not code-signed. Windows SmartScreen may show "Windows protected your PC"; choose **More info**, then **Run anyway**. Check the download against the published checksums first.

## Documentation

Contributors and coding agents start with [AGENTS.md](AGENTS.md).

| Document | Content |
| --- | --- |
| [docs/SRS.md](docs/SRS.md) | Software requirements specification |
| [docs/TEST-CATALOGUE.md](docs/TEST-CATALOGUE.md) | Test procedures, analysis and verdict rules (groups A to F) |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Technical solution, architecture, project structure |
| [docs/UX.md](docs/UX.md) | UI/UX design: personas, journeys, screens, interaction rules |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Development plan: releases, milestones, exit criteria |
| [docs/WORK-PACKAGES.md](docs/WORK-PACKAGES.md) | Work packages for implementation, with inputs, outputs and blockers |
| [docs/DECISIONS.md](docs/DECISIONS.md) | Decision register (confirmed, proposed, open) |
| [docs/DESIGN-REVIEW.md](docs/DESIGN-REVIEW.md) | First design review (historical; status in DECISIONS) |
| [docs/VERIFICATION.md](docs/VERIFICATION.md) | Open verification tasks |
| [docs/LICENSING.md](docs/LICENSING.md) | Licensing and legal constraints |
| [docs/REFERENCE-IMAGES.md](docs/REFERENCE-IMAGES.md) | Reference photo candidates and licence status |
| [docs/archive/handoff.md](docs/archive/handoff.md) | Original design handoff (baseline) |

## Principles

- Never report Pass for a test that did not run.
- Autofocus and metering findings are reported as Suspect with a confidence level, not as a binary verdict.
- Upload mode always works; USB control and vendor SDKs are optional. With a camera connected, the app does every step it can over USB.
- No vendor SDK is included in this repository, its source archives or CI builds. The official binary release is built by the maintainer against the vendor SDKs and bundles their runtime files (D-47), so it has every SDK feature. If you build from a clone, put each SDK under `sdk/<brand>/` (see `sdk/README.md`); without it the SDK features are reported as Not tested and the rest works.
- The app gives no buy or price advice.

## Trademarks

Brand and model names are used only to describe compatibility. They are trademarks of their respective owners.

## License

Apache-2.0. See [LICENSE](LICENSE).
