#!/usr/bin/env bash
# Generate index.test.html — a synthetic-data-only TEST BUILD of the browser
# companion with the network environment check bypassed, for GUI/UX testing
# on any machine. The shipped index.html is never modified.
set -euo pipefail
cd "$(dirname "$0")"

MARKER='const TEST_MODE = false;'
grep -qF "$MARKER" index.html || {
  echo "TEST_MODE marker not found in index.html — has the flag moved?" >&2
  exit 1
}

sed "s/$MARKER/const TEST_MODE = true;/" index.html > index.test.html

grep -qF 'const TEST_MODE = true;' index.test.html \
  && echo "Wrote index.test.html (TEST BUILD — synthetic data only)."
