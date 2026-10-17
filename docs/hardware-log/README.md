# Hardware log

One file per camera body and session: `<brand>-<model>-<yyyymmdd>.md`. Nothing in the project has
been run on a real camera yet; every `[Unverified]` item in the documents stays that way until a
log here records the result (see [VERIFICATION.md](../VERIFICATION.md)).

## Protocol for one body

Record the body, firmware, lens, Windows version, cable, connection used (WPD, libusb or SDK),
and for each step the result and any error text.

1. **Detection**: plug in with the USB mode the app names. Does the app find the body? Which
   backend was chosen? (V-13)
2. **Device data**: serial, firmware, battery, storage, shutter count. Does each value match the
   camera menu or a known-good reading? (V-05, V-20)
3. **Settings**: does the app change ISO, shutter speed, aperture and metering? Are the originals
   restored at the end? (FR-ACQ-06)
4. **Capture**: single shot, then a burst of 10. Are timestamps sub-second? (V-17) Do the files
   decode (V-14)?
5. **Focus**: does `InitiateCapture` fail or time out when the lens cannot focus? Which response
   code? (V-15, R-01)
6. **Live view**: does the helper see a covered sensor, an even field and the chart? (V-22)
7. **SDK** (when an SDK folder is set): which extra features work? (V-01, V-02, V-23)
8. **Usability**: can a user finish connected mode with nothing the cable could have done?
   (UX section 11)

Spike WP-40 repeats steps 1 to 4 on one Canon and one Sony body for each transport: WPD first,
then libusb, then a .NET helper, and records the decision.
