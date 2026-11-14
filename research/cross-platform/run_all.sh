#!/bin/sh
# The whole pipeline without model calls. Needs data/chatly_recording/ (python3 chatly.py) and optionally data/labels.json (python3 labels.py).
set -e
cd "$(dirname "$0")"
python3 world.py
python3 replay.py
python3 adapters.py
python3 analysis.py > /dev/null
python3 insights.py > /dev/null
python3 verify.py
