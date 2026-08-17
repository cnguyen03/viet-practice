#!/bin/bash
# Prepare macOS Internet Sharing to broadcast a Wi-Fi network with NO upstream
# internet connection — the offline case this project exists for (bus, car).
#
# Internet Sharing insists on having some connection to "share", so we create a
# dummy network service on the loopback interface and share that instead. No
# traffic actually flows through it; it exists to satisfy the requirement.
#
# Run:   sudo ./scripts/setup_hotspot.sh
# Undo:  sudo ./scripts/setup_hotspot.sh --remove

set -euo pipefail

SERVICE_NAME="AdHocSource"

if [[ "${1:-}" == "--remove" ]]; then
  echo "Removing the '$SERVICE_NAME' network service…"
  networksetup -removenetworkservice "$SERVICE_NAME" 2>/dev/null \
    || echo "  (it wasn't there — nothing to do)"
  echo "Done. Turn Internet Sharing off in System Settings if it's still on."
  exit 0
fi

if [[ $EUID -ne 0 ]]; then
  echo "This needs sudo: sudo $0" >&2
  exit 1
fi

if networksetup -listallnetworkservices | grep -qx "$SERVICE_NAME"; then
  echo "Network service '$SERVICE_NAME' already exists — leaving it alone."
else
  echo "Creating dummy network service '$SERVICE_NAME' on lo0…"
  networksetup -createnetworkservice "$SERVICE_NAME" lo0
fi

echo "Assigning it a manual IP so macOS treats it as active…"
networksetup -setmanual "$SERVICE_NAME" 10.10.10.1 255.255.255.255

cat <<'INSTRUCTIONS'

Done. Now finish in the GUI (macOS gives no CLI for this part):

  1. System Settings → General → Sharing
  2. Click the (i) next to "Internet Sharing"
  3. Share your connection from:  AdHocSource
  4. To devices using:           check "Wi-Fi"
  5. Wi-Fi Options… → set a network name and a WPA2 password → OK
  6. Toggle "Internet Sharing" on, and confirm the warning

Then join that Wi-Fi network from your phone and start the server:

  uv run uvicorn server.main:app --host 0.0.0.0 --port 8000

The server prints the exact URL to open on your phone (usually
http://192.168.2.1:8000). Bookmark it while you're still at home.

INSTRUCTIONS
