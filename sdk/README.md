# Local SDK folder

Put each vendor SDK in its own folder here: `canon/`, `sony/`, `nikon/`.

Nothing in these folders is ever committed: `.gitignore` here ignores everything except this file and the folder markers. Vendor SDK files must not be in the repository or a release (D-31). The app finds them at runtime when this folder is set as the SDK folder in settings.
