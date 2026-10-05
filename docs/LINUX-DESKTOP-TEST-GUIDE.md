# Linux and Browser Test Guide

This guide covers two separate ways to try Vault Folio:

1. **HTML model:** a browser demo for viewing and trying the interface with invented data only.
2. **Linux desktop test build:** the native app build for testing desktop UI and encrypted file save/open workflows.

Neither route is an audited production release. Do not enter sensitive or real inheritance information in either test build.

## HTML model: browser demo only

Grok is preparing a fuller HTML model so people can try the working interface in a browser. It is being developed for demonstration and test purposes. It is not the security-enforcing desktop app and cannot verify that Wi-Fi, Bluetooth, Ethernet, tethering, or other network paths are physically disabled. A browser also cannot guarantee RAM-only operation, prevent system/browser logging or screenshots, or ensure that data is not persisted by the operating system.

Use only invented sample answers and a new test-only passphrase. Never enter seed words, private keys, wallet descriptors, seed passphrases, recovery-share words, real names or contact information, exact storage locations, real family answers, or any other sensitive details. Treat any exported test file as disposable. Wait for the HTML build's own README and disclaimer before relying on its exact save/export behavior.

The existing browser-edition/index.html is an earlier companion prototype. It has browser-based encryption experiments, but it cannot enforce the native desktop security checks. It is not evidence that Grok's in-progress HTML model is ready or that any browser build is safe for real plans.

## Linux desktop test build

The reviewed archive csip-ubuntu-offline.zip is targeted at **Ubuntu 26.04, amd64, Python 3.14**. It contains the Python app and modules, test files, an installer, and Tkinter-related .deb packages. It is a target-specific experimental package, not a universal Linux build.

The archive's launcher uses **--ubuntu-test**, which bypasses the air-gap lock. Use invented data and a new test-only passphrase. This test mode is for trying the native interface and encrypted save/open flow; it does not establish RAM-only operation or protection from persistent storage.

### Package contents and known dependency gap

The archive includes:

- python3.14-tk
- libtcl8.6
- libtk8.6
- libxss1
- libxft2
- libxrender1

The application also imports Python cryptography, but the archive does not bundle its package. Check whether it is already available on the target before launching. The installer uses sudo dpkg -i on the included packages; it is not a complete dependency resolver.

### Try the Ubuntu archive

1. Extract the ZIP to a new folder.
2. Check the target OS, architecture, and Python:
   cat /etc/os-release
   dpkg --print-architecture
   python3 --version
   This archive is for Ubuntu 26.04 amd64 with Python 3.14. Stop if those do not match.
3. Check the crypto module:
   python3 -c 'import cryptography; print(cryptography.__version__)'
   If missing, prepare a matching offline package for this exact OS and Python target before continuing.
4. Run bash INSTALL-OFFLINE.sh. It requests administrator access to install its included Tkinter packages and then starts the test app.
5. Use only synthetic invented data. Test saving an encrypted file, closing the app, and reopening that test file.

Never enter a real plan, seed words, private keys, wallet descriptors, seed passphrases, recovery words, contact data, or a reused/real passphrase.

## Ubuntu releases and Debian

A .deb package set is specific to its distribution release, architecture, and often Python ABI. Do not mix Ubuntu and Debian packages or assume one release's packages work on another.

To prepare an offline bundle, use a connected preparation machine or matching official installation media to collect the target distribution's Python runtime, Tkinter module, Tcl/Tk libraries, cryptography package, and all transitive dependencies from the target's signed package sources. Transfer the complete package set by removable media. Validate package signatures/checksums and dependency closure before delivery; do not rely on dpkg -i output alone.

Required runtime pieces:

- Python 3.9+ compatible with the source
- matching Tkinter module and Tcl/Tk shared libraries
- Python cryptography and its runtime dependencies
- working graphical desktop

Verify after installation:

python3 -c 'import tkinter, cryptography; print("Tk", tkinter.TkVersion, "cryptography", cryptography.__version__)'

Create separate packages such as ubuntu-<release>-<arch> and debian-<release>-<arch>. Each should include a package manifest, SHA-256 checksums, source commit, install/launch scripts, target OS/Python details, and a clean-machine test record. The Ubuntu archive inspected here does not provide Debian compatibility.

## Build and test from source

On a matching Linux desktop with dependencies already installed:

python3 -m unittest discover -s tests -v
python3 vault-folio.py --self-test
python3 vault-folio.py --test-only-synthetic-questionnaire

The last command skips all environment checks and permits synthetic UI/save/open testing. Use invented data and a new test-only passphrase. It does not prove offline operation, RAM-only execution, swap status, or protection from persistent storage.

For the native app's intended security model, see RAM-SESSION.md and OPERATIONAL-SECURITY.md. Normal plan work requires a trusted nonpersistent live Linux environment. This test guide does not relax those requirements or certify a distribution, browser, package set, or machine.
