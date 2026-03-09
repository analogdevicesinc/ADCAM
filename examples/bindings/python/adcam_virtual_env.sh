#!/bin/bash

set -euo pipefail

# List of Debian packages to check and install
INTERNET_CONNECTION=false
host="8.8.8.8"
count=1
timeout=2

if ping -c "$count" -W "$timeout" "$host" > /dev/null 2>&1; then
  INTERNET_CONNECTION=true
else
  INTERNET_CONNECTION=false
fi

packages=(
  "v4l-utils"
  "build-essential"
  "libzmq3-dev"
  "cmake"
  "gcc"
  "g++"
  #"libopencv-contrib-dev"
  "libopencv-dev"
  "libgl1-mesa-dev"
  "libglfw3-dev"
  "doxygen"
  "graphviz"
  "python3.10-dev"
  "python3.13-dev"
  # Add more packages to this list
)

# Function to check if a package is installed
is_package_installed() {
  dpkg -s "$1" > /dev/null 2>&1
  return $? # Return 0 if installed, non-zero otherwise
}

# Loop through the list of packages
for package in "${packages[@]}"; do
  if ! is_package_installed "$package"; then
    echo "Package '$package' is not installed. Attempting to install..."
    if [ "$INTERNET_CONNECTION" = false ]; then
      echo "❗No internet connection. Please connect to the internet and try again❗"
      echo "Continuing with remainder of script, but the features may be limited..."
      break
    fi
    # Install the package without prompting (-y)
    sudo apt-get update > /dev/null 2>&1
    if sudo apt-get install -y "$package" > /dev/null 2>&1; then
      echo "Successfully installed '$package'."
    else
      echo "Warning: Error installing '$package' or package not available in repositories."
      # continue without failing the whole script
    fi
  fi
done

echo "Package check and installation complete."

# Setup Python venv
VENV_NAME="adcam_virtual_env"

# Prefer Python 3.10, otherwise attempt Python 3.13
CANDIDATES=(python3.10 python3.13)

PYBIN=""
for c in "${CANDIDATES[@]}"; do
  if command -v "$c" >/dev/null 2>&1; then
    PYBIN="$(command -v "$c")"
    break
  fi
done

if [[ -z "${PYBIN}" ]]; then
  echo "No suitable Python found. Please install python3.10 or python3.13 and retry." >&2
  exit 1
fi

# Get major.minor version (e.g., 3.10 or 3.13)
PYVER_FULL="$("$PYBIN" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
echo "Using $("$PYBIN" -V) at $PYBIN (detected version: $PYVER_FULL)"

# Ensure venv support (install pythonX.Y-venv if needed)
if ! "$PYBIN" -m venv --help >/dev/null 2>&1; then
  VENV_PKG="python${PYVER_FULL}-venv"
  echo "'venv' module missing for Python $PYVER_FULL. Attempting to install package: $VENV_PKG"
  if [ "$INTERNET_CONNECTION" = false ]; then
    echo "❗No internet connection to install $VENV_PKG. Please connect and re-run the script." >&2
    exit 1
  fi
  sudo apt-get update
  if sudo apt-get install -y "$VENV_PKG"; then
    echo "Installed $VENV_PKG."
  else
    echo "Failed to install $VENV_PKG. Try installing it manually and re-run the script." >&2
    exit 1
  fi
fi

# Remove existing venv if you want a fresh one (optional)
if [ -d "$VENV_NAME" ]; then
  echo "Virtual env '$VENV_NAME' already exists. Recreating it..."
  rm -rf "$VENV_NAME"
fi

# Create venv using the chosen python binary
"$PYBIN" -m venv "$VENV_NAME"

# Activate venv
# shellcheck disable=SC1091
source "$VENV_NAME/bin/activate"

echo "Virtual env '$VENV_NAME' created and activated."

echo "Installing requirements (this may take a while)..."

# Temporarily allow commands to fail so we can continue and summarize failures
set +e

# Upgrade pip (don't abort on failure)
python -m pip install --upgrade pip

# If requirements.txt exists, install each line separately and record failures.
if [ -f "./requirements.txt" ]; then
  FAILS=()
  mapfile -t REQS < ./requirements.txt

  for req in "${REQS[@]}"; do
    # Trim leading/trailing whitespace
    req_trim="$(echo "$req" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
    # Skip empty lines and comments
    if [ -z "$req_trim" ] || [ "${req_trim:0:1}" = "#" ]; then
      continue
    fi

    echo "Installing requirement: $req_trim"
    # shellcheck disable=SC2086
    python -m pip install $req_trim
    if [ $? -ne 0 ]; then
      echo "Failed to install: $req_trim"
      FAILS+=("$req_trim")
    fi
  done

  echo ""
  if [ "${#FAILS[@]}" -ne 0 ]; then
    echo "Summary: The following requirements failed to install (${#FAILS[@]}):"
    for f in "${FAILS[@]}"; do
      echo "  - $f"
    done
    echo "You can attempt to install them manually, or re-run the script after fixing network/repo issues."
  else
    echo "All requirements installed successfully."
  fi
else
  echo "requirements.txt not found in current directory; skipping pip install -r ./requirements.txt"
fi

# Re-enable exit-on-error for the remainder of the script
set -e

echo "All set."
