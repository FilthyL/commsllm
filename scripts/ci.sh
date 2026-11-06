#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
shopt -s nullglob globstar

echo '== actionlint =='
workflows=(.github/workflows/*.yml)
if ((${#workflows[@]})); then
  if ! command -v actionlint >/dev/null 2>&1; then
    # Optional bootstrap tooling may be absent on a minimal local machine.
    if command -v curl >/dev/null 2>&1 && command -v tar >/dev/null 2>&1 &&
       command -v sha256sum >/dev/null 2>&1; then
      actionlint_version=1.7.7
      platform="$(uname -s | tr '[:upper:]' '[:lower:]')"
      case "$(uname -m)" in
        x86_64) arch=amd64 ;;
        aarch64|arm64) arch=arm64 ;;
        *) arch=unsupported ;;
      esac
      if [[ "$platform" == linux || "$platform" == darwin ]] && [[ "$arch" != unsupported ]]; then
        tool_dir=$(mktemp -d)
        trap 'rm -rf "$tool_dir"' EXIT
        asset="actionlint_${actionlint_version}_${platform}_${arch}.tar.gz"
        release="https://github.com/rhysd/actionlint/releases/download/v${actionlint_version}"
        curl --fail --silent --show-error --location "$release/$asset" -o "$tool_dir/$asset"
        curl --fail --silent --show-error --location \
          "$release/actionlint_${actionlint_version}_checksums.txt" -o "$tool_dir/checksums.txt"
        (cd "$tool_dir"; grep "  $asset\$" checksums.txt | sha256sum --check --strict)
        tar -xzf "$tool_dir/$asset" -C "$tool_dir" actionlint
        export PATH="$tool_dir:$PATH"
      else
        echo 'warning: unsupported platform; skipping actionlint' >&2
      fi
    else
      echo 'warning: actionlint bootstrap tools absent; skipping actionlint' >&2
    fi
  fi
  if command -v actionlint >/dev/null 2>&1; then
    actionlint "${workflows[@]}"
  fi
fi

echo '== shellcheck =='
shell_scripts=(scripts/**/*.sh)
if ((${#shell_scripts[@]})); then
  if command -v shellcheck >/dev/null 2>&1; then
    shellcheck "${shell_scripts[@]}"
  else
    echo 'warning: shellcheck absent; skipping shellcheck' >&2
  fi
fi

echo '== labels JSON =='
if [[ -f comms/labels.json ]]; then
  python3 -m json.tool comms/labels.json >/dev/null
fi

echo '== Python tests =='
if [[ -d tests ]]; then
  python3 -m unittest discover -s tests -v
fi

echo '== comms lint =='
if [[ -f scripts/comms.py ]]; then
  python3 scripts/comms.py lint
fi
