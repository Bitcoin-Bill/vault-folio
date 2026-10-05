# Offline laptop

The app runs on an air-gapped laptop that is fully offline.

- Host: Signer
- User: l3tcl3ill
- OS: Ubuntu 26.04.1 LTS, Python 3.14
- No Wi-Fi, no Ethernet, no apt update, no pip.

Do not tell the user to run apt update, apt install from the network, or pip install.
Put every required .deb in the zip. Tkinter was missing; python3-cryptography was already installed.
