# Reference Photos for Visual Checks

Decision D-38: visual checks show real-world photos of each defect, from openly licensed sources only, with author, licence and source shown in the app. Target: 4 photos per defect. The maintainer adds or replaces photos with their own where needed.

## Status of this list

- Candidates were found with a web search restricted to Wikimedia Commons on 2026-10-17.
- `[Unverified]` Licence, author and suitability of every candidate. The session's network policy blocks `commons.wikimedia.org` and `upload.wikimedia.org`, so the file pages could not be opened and no image was downloaded. Licence notes below come from search summaries only.
- No candidate may ship until its file page has been checked and its licence recorded in `src/camera_preflight/gui/reference/ATTRIBUTION.md` (to be created).

## Acceptance rules for a photo

1. Licence: CC0, public domain, CC BY or CC BY-SA. Not accepted: non-commercial (NC), no-derivatives (ND) if cropping is needed, unclear licence.
2. Shows the defect clearly at the size used in the app (about 480 px wide).
3. No brand logo as the main subject, no people, no personal data.
4. Attribution string stored with the file: title, author, licence, source URL, changes made (crop, resize).

## Defects and candidates

| ID | Defect (check) | Candidates found | Count / target | Notes |
| --- | --- | --- | --- | --- |
| RP-01 | Lens fungus (F lens condition) | [File:Objektiv_fungus.jpg](https://commons.wikimedia.org/wiki/File:Objektiv_fungus.jpg) | 1 / 4 | Search summary: CC BY-SA 3.0 DE, author Jakob Ott, rear element with fungus |
| RP-02 | Haze or dust inside lens (F lens condition) | none | 0 / 4 | Maintainer photos likely needed |
| RP-03 | Scratched front element (F lens condition) | none | 0 / 4 | Maintainer photos likely needed |
| RP-04 | Dust spots in an image (B4 explanation) | [File:Dustspots_on_CMOS_sensor.jpg](https://commons.wikimedia.org/wiki/File:Dustspots_on_CMOS_sensor.jpg); [Category:Sensor_dust](https://commons.wikimedia.org/wiki/Category:Sensor_dust) (18 files per search summary) | 1+ / 4 | Category likely yields the remaining 3 |
| RP-05 | Scratch on sensor (blocker check, mount check) | none | 0 / 4 | |
| RP-06 | Damaged or misaligned mirror (blocker check) | none | 0 / 4 | Only household mirrors found |
| RP-07 | Worn or dirty lens contacts (mount check) | [File:EF-lens-mount.jpg](https://commons.wikimedia.org/wiki/File:EF-lens-mount.jpg); "Nikon F-Mount Lens Contacts.jpg" in [Category:Nikon_F-mount](https://commons.wikimedia.org/wiki/Category:Nikon_F-mount) | 2 / 4 | Show the healthy state, not a defect; useful as "what good looks like". Brand mounts: crop to avoid logos |
| RP-08 | Corrosion (battery terminals, contacts) | "Battery Terminal Corrision.jpg" in [Category:Corrosion](https://commons.wikimedia.org/wiki/Category:Corrosion); [File:W_pile_zinc_carbone_etats_de_corrosion.jpg](https://commons.wikimedia.org/wiki/File:W_pile_zinc_carbone_etats_de_corrosion.jpg) (search summary: CC BY-SA 2.5) | 2 / 4 | Generic batteries, not camera batteries |
| RP-09 | Dents, cracks from a drop (blocker check, body) | none | 0 / 4 | |
| RP-10 | Scratched screws, signs of opening (body) | none | 0 / 4 | |
| RP-11 | Peeling rubber grip (body) | none | 0 / 4 | |
| RP-12 | Dead or stuck pixel on LCD (screens) | [File:Lcd_display_dead_pixel.jpg](https://commons.wikimedia.org/wiki/File:Lcd_display_dead_pixel.jpg) (camera LCD); [File:Dead_LCD_20210515_063215.jpg](https://commons.wikimedia.org/wiki/File:Dead_LCD_20210515_063215.jpg) (search summary: CC0); [File:Dead-pixels.jpg](https://commons.wikimedia.org/wiki/File:Dead-pixels.jpg); [Category:Defective_pixels](https://commons.wikimedia.org/wiki/Category:Defective_pixels) | 3+ / 4 | Best-covered defect |
| RP-13 | Dust in the optical viewfinder (finder) | none | 0 / 4 | |
| RP-14 | Damaged shutter curtain (blocker check) | [File:Photo_camera_shutter.jpg](https://commons.wikimedia.org/wiki/File:Photo_camera_shutter.jpg); [File:Focal-plane_shutter.jpg](https://commons.wikimedia.org/wiki/File:Focal-plane_shutter.jpg) | 2 / 4 | Healthy shutters only; useful as reference |

Coverage: 6 of 14 defects have at least one candidate; none reaches 4. `[Inference]` Openly licensed photos of camera defects are rare; most defects will need maintainer photos (D-38).

## Next steps

1. Allow `commons.wikimedia.org`, `upload.wikimedia.org` and `api.openverse.org` in the environment's network settings, so licences can be verified, more sources searched (Openverse indexes Creative Commons images from many sites) and files downloaded.
2. Verify each candidate's file page; record attribution; reject anything that fails the acceptance rules.
3. Maintainer adds own photos for the defects left uncovered.
