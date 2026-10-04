# YubiKey access to the inheritance guide (experimental)

The YubiKey unlocks the **guide only**. This is not a Bitcoin wallet or signer.
No Bitcoin seeds, private keys, seed passphrases, wallet passwords, PINs or share
words belong in the application. Contacts, location hints and custody structure
are still private information worth encrypting.

## Independent unlock options

Any one enrolled method opens the file: a package passphrase, a compatible
YubiKey alone, or every answer in one custom 3–5-question set. You can enroll
several alternatives (up to 12 total). This is OR access, not multifactor.
There is no mandatory recovery code or passphrase-plus-key combination.
A lawyer may hold one key or one passphrase; family may use another route.

Method labels and question prompts are public. Questions should not disclose
private facts. Answers can be guessed offline with no enforceable retry limit;
the weakest enrolled method determines the guide's guessing resistance.
Owner/heir modes are viewing choices, not separate authorization roles.

## Compatibility and setup

Use a model with the **Yubico OTP HMAC-SHA1 challenge-response** application,
such as a compatible YubiKey 5. FIDO-only Security Key / Bio FIDO devices cannot
use this adapter. This is USB challenge-response, not WebAuthn, a passkey, NFC,
a static password or a one-time code. Confirm your exact model and firmware
with [Yubico's model guide](https://www.yubico.com/products/identifying-your-yubikey/).

1. Install the official YubiKey Manager CLI (`ykman`) and required USB permissions
   in your trusted offline environment. Prepare verified dependencies before
   isolating the machine. No application operation downloads anything.
2. Use a dedicated key and inspect existing OTP slots with `ykman otp info`.
   **Never overwrite a slot used by another application.** Vault Folio does not
   provision, reset, delete, or change device slots.
3. Only when slot 2 is unused and you intend to configure it, the official setup
   command is `ykman otp chalresp --touch --generate 2`. Keep the confirmation
   prompt; do not use `--force`. Provision an independent spare the same way,
   on its own unused slot. The setup utility may display the generated HMAC
   secret: treat that output as sensitive, avoid terminal logging, and do not
   paste it into this app. Do this on a trusted offline host.
4. Verify that calculating a response requires touching the device. The
   application's adapter cannot attest the configured touch policy. Also verify
   behavior for your exact OS, firmware and USB permissions before real use.

Vault Folio's only device command is:

```text
ykman otp calculate <1-or-2> <public-random-challenge-in-hex>
```

The response is captured in memory, never logged or placed on the command line.
The HMAC provisioning secret is never requested. Use only a trusted `ykman`
installation on a trusted PATH. The app waits up to 40 seconds per calculation;
cancelling prevents opening/saving, but an in-progress USB call may take until
the timeout to return.

Official command reference:
https://docs.yubico.com/software/yubikey/tools/ykman/OTP_Commands.html

## Owner workflow

At **Encrypt & export**, keep or remove the default passphrase row and add
passphrase, YubiKey, or family-question alternatives. Label each for its custodian
without disclosing private details. Select the correct existing OTP slot per key.
Each question set has 3–5 questions; all its answers are required. Confirm every
entered secret. Review the exact list before saving: old methods are not carried
over automatically when editing a previously opened guide.

Connect each requested key alone and touch when it flashes. Duplicate HMAC
secrets are rejected. The app self-decrypts through every configured method
before writing the ciphertext. Hardware operations run off the UI thread, check
the environment before/after and discard results after cancellation or lock.

Reopen the SAVED file separately using every intended method. Have an heir
rehearse finding the offline program, ciphertext and separate unlock custodian.
Keep the previous verified backup until this succeeds. Put the non-secret
discovery instructions OUTSIDE the encrypted guide.

## Can information be exfiltrated?

Yes, from a compromised host. Yubico documents that a configured challenge-response
secret is not extractable through the application interface. That does not mean
all data associated with an unlock stays inside the device:

- Provisioning happens on a host and can expose the initial secret.
- The response intentionally goes to the computer. It is reusable for that
  file's challenge and can unlock that copy without the physical key.
- The decrypted guide, derived keys and entered passphrase exist in host RAM.
  Malware can read them, capture screenshots or retain them for later upload.
- A touch shows user presence, not which application or challenge is trustworthy.
- A key carried daily can be lost, stolen or damaged. Key-only mode grants guide
  access to whoever holds both file and key.

Reference: https://docs.yubico.com/yesdk/users-manual/application-otp/challenge-response.html

Use a dedicated key and an offline trusted machine.
The app makes no network requests, but its checks cannot prove a hostile OS is
safe. Memory clearing is best effort; Python and browser garbage collection do
not guarantee secure erasure. Do not reuse a wallet passphrase as the package
passphrase. Unplugging the key does not close an already decrypted guide.

## Loss, rotation and recovery

If a key is lost, open with another enrolled method and export a NEW package
using your desired replacement methods. Each export uses new random encryption
material. Changing the guide does not revoke old copies: old unlock methods
can still open old files. Replacing a programmed OTP secret breaks that
key's access to all files encrypted for the previous secret.

There is no remote server, Yubico account, online validation service, password
reset, automatic legal release, death verification, or remote revocation.
The separately documented v2 format supports future recovery implementations.
This implementation remains experimental until real-device testing and
independent review are complete. Automated simulated-device tests are not
hardware certification.
