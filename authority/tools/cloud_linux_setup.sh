#!/usr/bin/env bash
# Linux setup for the cloud-agent notes in AGENTS.md.
# Install requirements-dev.txt into .venv, then point cc and c++ at system GCC.
# A venv avoids PEP 668 externally-managed-environment and the error from
# `pip install --user` inside a virtualenv. Packages are installed before the
# compiler switch. Running the script again is safe.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
venv="${root}/.venv"

if [[ ! -x /usr/bin/gcc || ! -x /usr/bin/g++ ]]; then
  echo "cloud_linux_setup: need /usr/bin/gcc and /usr/bin/g++" >&2
  exit 1
fi

if ! python3 -c 'import ensurepip' >/dev/null 2>&1; then
  sudo -n env DEBIAN_FRONTEND=noninteractive apt-get update
  sudo -n env DEBIAN_FRONTEND=noninteractive apt-get install -y python3-venv
fi

python3 -m venv "${venv}"
"${venv}/bin/python" -m pip install -r "${root}/requirements-dev.txt"

sudo -n update-alternatives --set cc /usr/bin/gcc
sudo -n update-alternatives --set c++ /usr/bin/g++
