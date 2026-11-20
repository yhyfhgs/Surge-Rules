#!/bin/sh
# Run on the target Mac after enabling its Surge configuration.
# Change only DNS acceptance; preserve identity, advertised routes and exit node.
set -eu
if command -v tailscale >/dev/null 2>&1; then
    exec tailscale set --accept-dns=false
fi
if [ -x /Applications/Tailscale.app/Contents/MacOS/Tailscale ]; then
    exec env TAILSCALE_BE_CLI=1 /Applications/Tailscale.app/Contents/MacOS/Tailscale set --accept-dns=false
fi
echo 'Tailscale CLI not found. Disable "Use Tailscale DNS settings" in Tailscale preferences.' >&2
exit 1
