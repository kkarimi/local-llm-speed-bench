#!/usr/bin/env bash
# Exercise the piped installer against the exact local checkout in CI.
set -euo pipefail
repo=$(git rev-parse --show-toplevel)
tmp=$(mktemp -d)
trap 'rm -rf -- "$tmp"' EXIT
export XDG_DATA_HOME="$tmp/app data" HOME="$tmp/home" LLM_BENCH_REVISION
LLM_BENCH_REVISION=$(git rev-parse HEAD)
export GIT_CONFIG_COUNT=1
export GIT_CONFIG_KEY_0="url.file://$repo.insteadOf"
export GIT_CONFIG_VALUE_0=https://github.com/kkarimi/local-llm-speed-bench.git
launcher="$HOME/.local/bin/llm-speed-bench"
cd "$tmp"
bash < "$repo/install.sh"
"$launcher" --help | grep 'bench'
python3 "$repo/tests/wizard-smoke.py" "$launcher"
bash < "$repo/install.sh"
[[ -x "$launcher" ]]
# A failed update must leave the working command intact.
if LLM_BENCH_REVISION=invalid bash < "$repo/install.sh"; then exit 1; fi
"$launcher" report --help >/dev/null
