#!/bin/sh
cd "$(dirname "$0")"
exec python3 vault-folio.py --ubuntu-test
