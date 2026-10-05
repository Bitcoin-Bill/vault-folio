# Linux and browser test guide

Vault Folio is an offline desktop application. The real guide is `vault-folio.py`. It is meant for an air-gapped machine. A normal launch stays locked unless Linux reports no default route, no active network interface, and no Wi-Fi or Bluetooth hardware.

The browser page is a public preview of the flow. It is already in this repo at `browser-edition/app.html`. It is not the desktop app. It does not check the machine, and it does not write a desktop Vault Folio file. Never enter a seed phrase, a private key, a real passphrase, or a private plan there. A device name such as SeedSigner is fine.

Neither path is a certified release. Use invented answers.

## Browser preview

Open `browser-edition/app.html` in a browser. The warning stays at the top. The page walks the interview, the sheets, a risk note, a passphrase window, and a short heir view.

## Ubuntu 26.04 test package

`csip-ubuntu-offline.zip` is for Ubuntu 26.04, amd64, Python 3.14. It is not a package for every Linux machine. The laptop it was built for is air-gapped, so the zip includes the window library and its related packages:

- python3.14-tk
- libtcl8.6
- libtk8.6
- libxss1
- libxft2
- libxrender1

It does not include the Python cryptography package. That package was already installed on the tested laptop. If a machine does not already have it, the app cannot seal a file until a matching offline package is added to the zip. Do not tell that laptop to run apt update or pip.

The launcher uses `--ubuntu-test`. That skips the air-gap lock so the full guide and encrypted save can be tried. It does not make the machine an offline session. Use invented answers and a new test passphrase.

1. Unzip the archive into a new folder.
2. Confirm Ubuntu 26.04, amd64, and Python 3.14.
3. Run `bash INSTALL-OFFLINE.sh`.
4. Save an encrypted test file, quit, and open it again.

## From source

On a Linux desktop that already has Tk and cryptography:

```bash
python3 -m unittest discover -s tests -v
python3 vault-folio.py --self-test
python3 vault-folio.py --ubuntu-test
```

`--ubuntu-test` skips the air-gap lock and keeps the normal encrypted save. `--test-only-synthetic-questionnaire` skips the lock and writes only a marked synthetic file. A normal launch still belongs on a nonpersistent live Linux session with networking actually off. See `docs/RAM-SESSION.md`.
