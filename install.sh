#!/usr/bin/env bash
# Install from the public repository into the current user's home directory.
set -euo pipefail

install_bench() {
  local python=${PYTHON:-python3}
  local root="${XDG_DATA_HOME:-$HOME/.local/share}/local-llm-speed-bench/releases"
  local bindir="$HOME/.local/bin"
  local repo=https://github.com/kkarimi/local-llm-speed-bench.git
  local ref=${LLM_BENCH_REVISION:-refs/heads/main}
  local command revision release
  for command in git npm node "$python"; do
    command -v "$command" >/dev/null || { echo "Missing command: $command" >&2; return 1; }
  done
  "$python" -c 'import sys; sys.exit(sys.version_info < (3, 9))' || { echo 'Python 3.9+ is required' >&2; return 1; }
  node -e 'const [major, minor] = process.versions.node.split(".").map(Number); process.exit(Number(major < 22 || (major === 22 && minor < 18)))' || { echo 'Node.js 22.18+ is required' >&2; return 1; }
  if [[ "$ref" != refs/heads/main && ! "$ref" =~ ^[0-9a-f]{40}$ ]]; then
    echo 'LLM_BENCH_REVISION must be a full commit SHA' >&2
    return 1
  fi
  mkdir -p "$root" "$bindir"
  stage=$(mktemp -d "$root/.install.XXXXXXXX")
  trap 'rm -rf -- "$stage"' EXIT
  git -C "$stage" init -q
  git -C "$stage" fetch --quiet --depth=1 "$repo" "$ref"
  git -C "$stage" checkout --quiet --detach FETCH_HEAD
  revision=$(git -C "$stage" rev-parse HEAD)
  release="$root/$revision"
  if [[ ! -d "$release" ]]; then
    (cd "$stage" && npm ci --omit=dev --ignore-scripts --no-fund --no-audit &&
      node --input-type=module -e 'await import("@astrojs/cli-kit")' &&
      "$python" lab.py --help >/dev/null)
    rm -rf -- "$stage/.git"
  fi
  "$python" - "$stage" "$release" "$bindir" <<'PY'
import os
import sys
import tempfile
from pathlib import Path

stage, release, bindir = map(Path, sys.argv[1:])
launcher = bindir / 'llm-speed-bench'
if os.path.lexists(launcher):
    target = launcher.resolve()
    if not (launcher.is_symlink() and target.parent.name == 'bin' and
            target.name == launcher.name and target.parent.parent.parent == release.parent.resolve()):
        sys.exit(f'Existing command belongs to another installation: {launcher}')
if not release.exists():
    try:
        stage.rename(release)
    except OSError:
        if not release.is_dir():
            raise
with tempfile.TemporaryDirectory(dir=bindir) as tmp:
    link = Path(tmp) / launcher.name
    link.symlink_to(release.resolve() / 'bin' / launcher.name)
    os.replace(link, launcher)
PY
  echo "Installed llm-speed-bench at $revision"
  case ":$PATH:" in
    *":$bindir:"*) echo 'Run llm-speed-bench to start.' ;;
    *) printf 'Run "%s/llm-speed-bench" or add "%s" to PATH.\n' "$bindir" "$bindir" ;;
  esac
}

install_bench </dev/null
