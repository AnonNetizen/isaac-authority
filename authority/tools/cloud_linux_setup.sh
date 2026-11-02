#!/usr/bin/env bash
# Linux setup for the cloud-agent notes in AGENTS.md.
# Points cc and c++ at system GCC, then installs requirements-dev.txt.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

if [[ ! -x /usr/bin/gcc || ! -x /usr/bin/g++ ]]; then
  echo "cloud_linux_setup: need /usr/bin/gcc and /usr/bin/g++" >&2
  exit 1
fi

sudo -n update-alternatives --set cc /usr/bin/gcc
sudo -n update-alternatives --set c++ /usr/bin/g++

python3 -m pip install --user -r "${root}/requirements-dev.txt"
