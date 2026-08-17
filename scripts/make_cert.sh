#!/bin/bash
# Generate a self-signed TLS cert for the local server.
#
# Why this is needed: browsers only expose the microphone (getUserMedia) on a
# "secure context". http://localhost counts, but http://192.168.x.x does NOT —
# so the phone cannot record over plain HTTP. Serving HTTPS with this cert is
# what makes mic capture possible on the phone.
#
# Run: ./scripts/make_cert.sh

set -euo pipefail

cd "$(dirname "$0")/.."
CERT_DIR="certs"
mkdir -p "$CERT_DIR"

# The cert must name every address the phone might use, since browsers check
# the address against the cert's SANs. 192.168.2.1 is the usual macOS
# Internet Sharing address; the rest are whatever this Mac has right now.
SANS="DNS:localhost,IP:127.0.0.1,IP:192.168.2.1"
for iface in bridge100 en0 en1; do
  ip=$(ipconfig getifaddr "$iface" 2>/dev/null || true)
  [ -n "$ip" ] && SANS="$SANS,IP:$ip"
done

echo "Issuing cert for: $SANS"

openssl req -x509 -newkey rsa:2048 -nodes \
  -keyout "$CERT_DIR/key.pem" \
  -out "$CERT_DIR/cert.pem" \
  -days 825 \
  -subj "/CN=viet-practice local" \
  -addext "subjectAltName=$SANS" \
  2>/dev/null

chmod 600 "$CERT_DIR/key.pem"

cat <<INSTRUCTIONS

Wrote $CERT_DIR/cert.pem and $CERT_DIR/key.pem (both gitignored).

The server will now serve HTTPS automatically. Your phone will warn that the
certificate is untrusted the first time — that is expected for a self-signed
cert.

  iPhone: open the https:// URL, tap "Show Details" -> "visit this website".
          If Safari still refuses the microphone, install the cert properly:
          AirDrop $CERT_DIR/cert.pem to the phone, then
          Settings -> General -> VPN & Device Management -> install the profile,
          then Settings -> General -> About -> Certificate Trust Settings ->
          turn it on for this cert.

  Android: open the URL and tap "Advanced" -> "Proceed".

Do this once at home, while you still have a working network.

INSTRUCTIONS
