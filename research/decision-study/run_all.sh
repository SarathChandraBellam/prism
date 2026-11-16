#!/bin/sh
# The whole decision study. No model calls. Needs the round 4 data (../cross-platform/data).
set -e
cd "$(dirname "$0")"
python3 conform.py > /dev/null
for s in coverage tasks sampling seats demand cards; do python3 "$s.py" > /dev/null; done
echo "ok: data/*.md and data/*.json rebuilt"
