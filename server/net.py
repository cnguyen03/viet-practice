import subprocess

# bridge100 is the interface macOS Internet Sharing creates for the Wi-Fi
# hotspot; en0 is normal Wi-Fi. Hotspot wins so the printed URL is the one the
# phone should actually use during an offline session.
CANDIDATE_INTERFACES = ("bridge100", "en0", "en1")


def lan_addresses() -> list[tuple[str, str]]:
    """Return [(interface, ip)] for interfaces that currently have an IPv4 address."""
    found = []
    for iface in CANDIDATE_INTERFACES:
        try:
            result = subprocess.run(
                ["ipconfig", "getifaddr", iface],
                capture_output=True,
                text=True,
                timeout=2,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        ip = result.stdout.strip()
        if ip:
            found.append((iface, ip))
    return found


def startup_banner(port: int, tls: bool) -> str:
    scheme = "https" if tls else "http"
    lines = ["", "  Vietnamese practice server is up.", ""]
    addresses = lan_addresses()
    if addresses:
        lines.append("  Open on your phone:")
        for iface, ip in addresses:
            label = " (hotspot)" if iface == "bridge100" else ""
            lines.append(f"    {scheme}://{ip}:{port}{label}")
    else:
        lines.append("  No LAN address found — is the hotspot or Wi-Fi on?")
    lines += ["", f"  On this laptop: {scheme}://localhost:{port}"]
    if not tls:
        lines += [
            "",
            "  NOTE: serving plain HTTP, so the phone's microphone will be",
            "  blocked. Run ./scripts/make_cert.sh to enable HTTPS.",
        ]
    lines.append("")
    return "\n".join(lines)
