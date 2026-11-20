# Run on the target Windows machine after enabling its Mihomo configuration.
# Change only DNS acceptance; preserve identity, advertised routes and exit node.
$ErrorActionPreference = 'Stop'
$tailscaleCommand = Get-Command tailscale.exe -ErrorAction SilentlyContinue
if ($tailscaleCommand) {
    $tailscaleExecutable = $tailscaleCommand.Source
} else {
    $tailscaleExecutable = Join-Path $env:ProgramFiles 'Tailscale\tailscale.exe'
}
if (-not (Test-Path -LiteralPath $tailscaleExecutable)) {
    throw 'Tailscale CLI not found. Disable "Use Tailscale DNS" in the Tailscale tray menu.'
}
& $tailscaleExecutable set --accept-dns=false
if ($LASTEXITCODE -ne 0) {
    throw "Tailscale DNS preference was not changed successfully (exit $LASTEXITCODE)."
}
