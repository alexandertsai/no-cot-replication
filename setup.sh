#!/usr/bin/env bash
set -euo pipefail
TASK_ROOT="$(cd "$(dirname "$0")" && pwd)"
BENCH_ROOT="${NOCOT_BENCH:-$(dirname "$TASK_ROOT")/nocot-bench}"
BENCH_COMMIT=beb2ffcf73b657a445e8a7b797d7c9b0e249b570
if [ ! -d "$BENCH_ROOT/.git" ]; then
  git clone https://github.com/neelnanda-io/nocot-bench.git "$BENCH_ROOT"
fi
if [ "$(git -C "$BENCH_ROOT" rev-parse HEAD)" != "$BENCH_COMMIT" ]; then
  echo "Expected upstream commit $BENCH_COMMIT. Set NOCOT_BENCH to a checkout at that commit." >&2
  exit 1
fi
cd "$BENCH_ROOT"
sha256sum -c data/NOCOT_DATA_ZIP.sha256
unzip -oq -P lantern-orchard-pebble data/nocot_data.zip
python -m nocot.tests.test_smoke
