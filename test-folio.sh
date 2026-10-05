#!/bin/sh
# Test launch. Skips the air-gap gate. Saves only a marked synthetic file.
# Use invented answers and a new test passphrase. Do not use a real plan.
cd "$(dirname "$0")"
exec python3 vault-folio.py --test-session
