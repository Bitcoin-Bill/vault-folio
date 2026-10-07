# RAM-only guide creation and viewing

The real-plan desktop workflow now requires a **trusted nonpersistent live Linux
session**, with no active swap, no networking and process dump protection. Normal
installed macOS/Windows/Linux sessions do not satisfy this policy. There is no
“continue anyway” override. The browser edition remains a demonstration only.

The guide is assembled and decrypted in memory. The application deliberately
writes only the encrypted `.csp.json` file the user selects. No autosave, plaintext
export, local database, history, application logs or plaintext temp files are
created. Saving uses a transient encrypted sibling file for atomic replacement. Copy all `folio_*.py` modules alongside `vault-folio.py`; local bytecode
writing is disabled before importing them. Dependency installation should happen
in the prepared live image, not while entering a real guide.

## What the app checks

`folio_memory.py` checks Linux `/proc/swaps`, disables core dumps for the Python
process with `RLIMIT_CORE=0` and `PR_SET_DUMPABLE=0`, and checks mount information
using `findmnt`. Root, home, temp, `/var/tmp`, `/var/log` and configured XDG paths
must be tmpfs/ramfs or overlay filesystems whose writable upper layer resolves
to tmpfs/ramfs. Missing, inaccessible or unsupported mount topology blocks use.
The network/RAM checks repeat during the session and at hardware operation
boundaries. Export destinations may be persistent removable media because only
ciphertext is written there.

These checks establish only what the operating system reports. They do not
prove the kernel, firmware, desktop, display server, Python runtime or dependency
chain is trustworthy. A hostile OS can lie. They do not detect all external
logging, screenshots, VM snapshots or physical RAM acquisition. A live image
with an unusual layout may be rejected even if it is otherwise safe; inspect
and add a tested adapter rather than bypassing the policy.

## Session procedure

1. Boot a verified live Linux image with persistence disabled, on trusted hardware
   without radios or connected network adapters. Prefer a dedicated machine.
2. Disable swap and hibernation at the OS level before opening a guide. A tmpfs
   directory alone is insufficient: tmpfs can use swap. The app only checks;
   it does not silently change machine-wide settings or erase disk files.
3. Use RAM-backed home/temp/system writable layers. Do not enable persistent
   storage, screen recording, remote access or clipboard synchronization.
4. Create the guide and save ONLY the encrypted file to the chosen removable
   drive. Use a neutral filename if the plan title is sensitive; filenames and
   filesystem timestamps are not encrypted by this format.
5. Reopen the saved file and verify it using the intended heir unlock route.
6. **Clear session** drops app references and destroys the main UI. Closing the
   app also drops its active plan. Neither action is a guaranteed memory wipe.
7. Fully shut down the live session; do not sleep or hibernate. Remove the media.
   Follow the live OS's memory-sanitization procedures if your threat model
   includes physical memory capture.

## Permanent erasure is not a promise this app can make

Python, Tk, cryptography libraries, the OS and graphics system can retain copies
of strings or plaintext buffers. Dropping references and garbage collection do
not overwrite every copy. Power-off is part of the operational procedure, but
RAM remanence/cold-boot attacks mean “instant permanent deletion” is still not an
absolute guarantee. The app cannot erase traces created by a previous session
that ran on a persistent OS. This design avoids intentional plaintext writes;
it is not a forensic erasure tool.

A future hardened live image and independently reviewed native memory handling
would be separate work. Hardware/live-image acceptance testing is outstanding
for this preview. Automated checks simulate supported/unsupported mount states;
they do not certify any live distribution.

## When the gate blocks launch

The startup gate lists one row per check — PASS, FAIL or BLOCKED. Read the
failing row first; it identifies the failed check or unavailable information. The five checks are: no default
route, no active network interface, no Wi-Fi hardware, no Bluetooth hardware,
and the RAM-session row (swap disabled, process dump protection active, and
root, home, temp, `/var/tmp`, `/var/log` and configured XDG paths verifiably
RAM-backed).

Common causes, in rough order of likelihood:

1. **Installed Ubuntu (or any installed OS).** A disk-backed home folder and
   active swap can never pass the RAM-session row, no matter how much network
   hardware is removed. This is the policy working, not a fault. To try the
   interface on an installed Ubuntu system, launch with
   `python3 vault-folio.py --ubuntu-test` (or `sh START-UBUNTU-TEST.sh`), which
   skips the lock behind an UBUNTU TEST banner; use invented data only. The
   real workflow requires the nonpersistent live session described above.
2. **Swap auto-activated by the live session.** Live images may enable a swap
   partition found on the machine's internal disk. Run `sudo swapoff -a`
   before launching, then CHECK AGAIN.
3. **Bluetooth survived the Wi-Fi card.** Bluetooth is often a separate
   function on the same combo card or on the motherboard; the gate checks
   `/sys/class/bluetooth`. Remove the adapter or disable it in firmware setup.
4. **A default route outlived the hardware.** Routes can remain after a card
   is removed. The gate screen's TURN NETWORKING OFF AND CHECK button asks the
   OS to drop networking and attempts to delete any remaining default route,
   then re-checks. The request may fail; read the result and gate rows.
5. **A wired Ethernet interface.** An active cable-connected NIC fails the
   interface and route rows; unplug it.
6. **A check the OS cannot answer.** Missing tools or unreadable system files
   cause the gate to fail closed (the row may show FAIL rather than BLOCKED);
   they never pass silently. Verify the live image provides the required
   tools, including `findmnt`, and exposes the relevant system files. A live
   image alone does not guarantee that every check will pass.

## Temporary questionnaire demo mode

The air-gap transfer bundle includes a synthetic test mode. It skips all
environment checks so the interface and encrypted save/open flow can be tried on
unsupported live-session layouts. It saves only passphrase-protected VAULTFOLIO/2
files carrying a `syntheticTest` marker, and opens only marked files with that
passphrase method. It does not offer YubiKey enrollment or unlock. Normal mode
refuses marked test files. Use invented answers and a new test passphrase only;
never enter a real inheritance plan or reuse a real passphrase. The file is
encrypted, but this mode offers no offline, swap, or RAM-session protection and
does not establish that memory is nonpersistent. A normal launch keeps every
environment check and fails closed.

Primary references:
- Linux tmpfs and swap: https://docs.kernel.org/filesystems/tmpfs.html
- Process dumpability: https://man7.org/linux/man-pages/man2/pr_set_dumpable.2const.html
- Core dump limits: https://www.man7.org/linux/man-pages/man2/getrlimit.2.html

The external `ykman` executable also handles a response in RAM. Python process
hardening does not prove all subprocesses or their dependencies are dump-proof;
the trusted live OS must enforce session-wide nonpersistence.
