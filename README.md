# surge-rules

Surge rule lists with a generated Mihomo/Clash mirror. Edit [lists/](lists/) for
rule content and [config/routing.json](config/routing.json) for list order,
policies and modifiers. Routing is first-match-wins.

## Use

```text
Surge:  https://cdn.jsdelivr.net/gh/yhyfhgs/surge-rules@main/lists/<Name>.list
Mihomo: https://cdn.jsdelivr.net/gh/yhyfhgs/surge-rules@main/clash/<Name>.list
```

This is the domain/IP-separated v2 layout. Upgrade the rule sequence and list
files together; old mixed-list configurations should remain on their previous
commit until their coordinated upgrade. Production profiles use `@main`;
immutable URLs support coherent upgrades and verification.

Mihomo users can merge [clash/rule-providers.yaml](clash/rule-providers.yaml)
and supply their own policy groups. Follow the [Clash deployment contract](docs/CLASH.md)
for DNS, TUN and runtime limits. Files under `clash/` are generated.

## Device-scoped remote lists

[Optional device overlays](docs/DEVICE-OVERLAYS.md) cover campus access,
Tailscale, Macmini gateway services and the UK AI exceptions without changing
global ownership. Maintain `config/device-overlays.json` and its public sources;
`overlays/surge/` and `overlays/clash/` are generated, distributed via the same
GitHub/jsDelivr release as `lists/` and `clash/`. Private device credentials,
listener guards, process exemptions and deployment settings stay outside Git.

```bash
python3 tools/device_overlays.py
python3 tools/device_overlays.py --check --native
```

## Maintain

Assign each rule to one owner, keep domain rules before the encrypted-resolution
IP stage, and preserve list-order dependencies. Regional IP selectors subtract
the DIRECT protection sets; matching modifiers live in the v2 manifest. The local `../Surge.conf` contains private settings;
the renderer replaces only `[Rule]`. `tools/prepare_profiles.py` additionally
prepares reviewed DNS/group changes and verifies private proxy/certificate
sections remain intact. It never activates a candidate.

The [maintenance guide](docs/MAINTENANCE.md#validate-a-change) is the single
command reference for candidate validation, MMDB analysis and publication.
For a quick source/mirror check:

```bash
python3 tools/sort_lists.py --check
python3 tools/surge2clash.py --check
```

| Reference | Contents |
|---|---|
| [Architecture](docs/ARCHITECTURE.md) | Ownership, ordering, DNS invariants and analyzer output |
| [Maintenance](docs/MAINTENANCE.md) | Edit, regenerate, validate, debug and release |
| [Surge skill and CLI](docs/SURGE-CLI.md) | Global agent setup, CLI discovery, diagnostics and upgrade checks |
| [Current decisions](docs/DECISIONS.md) | Retained ownership decisions, evidence and unresolved verification |
| [Tests](tests/README.md) | Offline and live test entry points, data and limits |
| [Sources](SOURCES.md) / [lock](sources.lock.json) | Upstream provenance and reproducible inputs |
| [Changelog](CHANGELOG.md) | Batch decisions, validation and historical records |

Current rule and test counts come from tool output. Keep one current document
per subject; historical plans, superseded evidence and detailed old logs remain
in Git history, linked from the decision record and changelog. Put private
operating notes and diagnostics outside this repository.
