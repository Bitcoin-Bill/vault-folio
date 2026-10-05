# Linux Desktop Test Build Guide (Ubuntu and Debian)

This guide describes the **experimental desktop test build** of Vault Folio and how contributors can reproduce it. It is intended for synthetic UI and encrypted save/open testing, and as a starting point for Linux packaging work.

## Status and compatibility

The checked-in source requires Python 3.9 or newer, Tkinter, and the Python `cryptography` package. A working app build was supplied as `csip-ubuntu-offline.zip` for **Ubuntu 26.04, amd64, Python 3.14**. That archive includes Tkinter-related Debian packages and an installer that invokes Ubuntu's `dpkg`. Treat it as a build for that specific target only.

The archive does not establish compatibility with other Ubuntu releases, Debian, other architectures, or other Python versions. Debian and Ubuntu package filenames and dependency versions differ. Do not install a package set for the wrong release. The example archive's packages and script may be reviewed as a reference, but the reproducible package set must be assembled from the target release's own signed repositories or matching installation media.

This desktop test launch uses `--ubuntu-test`. It skips CSIP's air-gap lock. Do not use it for real plans or secrets. For normal plan use, consult [RAM-SESSION.md](RAM-SESSION.md) and its strict nonpersistent live Linux requirements. The Ubuntu test build is not an audited or hardened release.

## What is included in the supplied test archive

The archive contains the Python application and companion modules, test files, `INSTALL-OFFLINE.sh`, and these Ubuntu 26.04 amd64 packages:

- `python3.14-tk`
- `libtcl8.6`
- `libtk8.6`
- `libxss1`
- `libxft2`
- `libxrender1`

The app also imports `cryptography). The supplied archive does not contain a `python3-cryptography` package: that may be provided by the target Ubuntu image, but must be checked on each installation. The installer runs `sudo dpkg -i` for the included packages and starts the app with `--ubuntu-test`; it does not perform a complete dependency resolver or prove that every system dependency is satisfied.

## Try the supplied Ubuntu 26.04 amd64 bundle

1. Extract the ZIP into a new folder.
2. Open a terminal in that folder.
3. Check OS, architecture, and Python version:
   ```sh
   cat /etc/os-release
   dpkg --print-architecture
   python3 --version
   ```
   Proceed only with Ubuntu 26.04 amd64 and Python 3.14. Stop if these do not match.
4. Check the crypto dependency before installation:
   ```sh
   python3 -c 'import cryptography; print(cryptography.__version__)'
   ```
   If it is missing, do not use the launcher yet; provide a matching offline `python3-cryptography` package set for this exact OS/Python target.
5. Run `bash INSTALL-OFFLINE.sh`. The script requests administrator privileges to install the bundled Tkinter packages, then launches the GUI.
6. Use synthetic, invented questionnaire content and a new test-only passphrase. Save a test encrypted file, close the app, reopen it, and verify the test workflow.

The supplied launcher currently invokes `--ubuntu-test`, which skips the air-gap lock. Treat all data entered in that mode as disposable synthetic test data. Do not enter a real inheritance plan, seed words, private keys, wallet descriptors, seed passphrases, recovery words, contact data, or a real passphrase.

## Debian and other Ubuntu releases

There is no universal Linux `.deb` set. For a connected *preparation* machine, identify the exact target OS release and architecture, then download all required packages and their transitive dependencies from that distribution's signed package repository or official installation media. Transfer the complete package directory to the target by removable media and install locally with `dpkg -i ./*.deb`; resolve any missing dependencies using packages prepared for that same release and architecture. Never mix Ubuntu and Debian package sets or versions.

Required runtime components:

- Python 3.9+ compatible with the app
- the matching Tkinter module and Tcl/Tk shared libraries
- Python `cryptography` and its native/runtime dependencies (package names vary by release)
- a working graphical desktop session

After installation, verify the runtime before starting:

```sh
python3 -c 'import tkinter, cryptography; print("Tk", tkinter.TkVersion, "cryptography", cryptography.__version__)'
```

For a new Debian target, create and validate a separate Debian-specific bundle and instructions; do not reuse the Ubuntu 26.04 archive. Record the exact `/etc/os-release`, architecture, Python version, package versions, package checksums, and test results alongside each bundle.

## Building from source

On a matching Ubuntu or Debian desktop with development dependencies installed:

```sh
python3 -m unittest discover -s tests -v
python3 vault-folio.py --self-test
python3 vault-folio.py --test-only-synthetic-questionnaire
```

The last command is a synthetic UI/save/open mode. Use invented answers and a new test-only passphrase. It skips all environment checks and does not prove offline operation, RAM-only execution, swap status, or protection from persistent storage. Read [OPERATIONAL-SECURITY.md](OPERATIONAL-SECURITY.md) and [RAM-SESSION.md](RAM-SESSION.md) before evaluating the normal workflow.

Contributors should keep each platform package reproducible and separate: `ubuntu-<release>-<arch>`, `debian-<release>-<arch>`. Include the source commit, package manifest, SHA-256 checksums, setup/launch scripts, and a clean-machine validation record. Do not label a bundle “working” until the listed OS/Python/dependencies and GUI save/reopen workflow have been exercised.
