# Optional public device overlays

`config/device-overlays.json` is the single composition manifest for this
**optional** distribution layer. It does not add lists to the 53-list common
manifest, change global domain ownership, reorder common rules, assign policies,
or generate a device configuration. The private profile builder remains
responsible for selecting overlays and preserving device-specific behavior.

## Public and private boundary

Publish only reviewed, generic service selectors. The source files under
`overlays/sources/` contain policy-free rules and English comments. The builder
never reads archived profiles, inventories, traffic, or private local lists.
The original private evidence was used for a one-time scoped selector review,
not made into a reproducible private-file dependency.

Deliberately **not** exported:

- Process names, process exemptions, listener/source-address/client guards, node
  names, private endpoints, credentials, certificates, and traffic records.
- Individual tailnets, peer names/addresses, subnet-router routes, private tunnel
  hostnames, and proxy-server bypass rules.
- Rules that block QUIC or UDP/443. A profile's independent MITM
  `auto-quic-block` setting is not a rule overlay and stays with that profile.

The standard `100.64.0.0/10` and `fd7a:115c:a1e0::/48` protocol allocations are
public selectors, not peer inventory. The owner explicitly approved the single
campus destination `10.129.167.101/32` for this public overlay. Its source comment
is deliberately neutral; no server identity or purpose is published. These are
narrow validation exceptions, not permission to publish other private networks.

A policy-free public selector cannot preserve a removed client guard by itself.
On a gateway, keep the existing private source/listener condition around the
selected overlay call. Keep reasoned desktop transport process exemptions in
the private builder. Do not replace either with an unconditional public rule.
Keep these device-local boundaries in the private inventory and validated
profile; never infer that a public list replaces listener authorization.

## Composition and outputs

Every row produces both `overlays/surge/<Name>.list` and
`overlays/clash/<Name>.list`. The latter is **Mihomo text-classical**, not a YAML
`payload:` document, domain-only provider, or ipcidr provider.

| Name | Kind | Composition / intended scope |
|---|---|---|
| `TailscaleWebsiteDNS` | domain | The four existing exact proxy-DNS exceptions; DNS-only selection, narrower than routing. |
| `TailscaleProxy` | domain | Common 13 website/account/log exact hosts; no blanket control suffix. |
| `TailscaleCampusProxy` | domain | `TailscaleProxy` plus the archived relay wildcard and five exact relay hosts; campus alternative, not an additional base call. |
| `TailscaleNetwork` | domain | The complete `ts.net` namespace, without tailnet enumeration. |
| `TailscaleNetworkIP` | ip | The two standard Tailscale allocations, with native `no-resolve`. |
| `TailscaleControl` | domain | `tailscale.com`, `tailscale.io`, `tailscale.net` suffix fallbacks. |
| `CloudflareTunnel` | domain | Only `argotunnel.com`. |
| `CloudflareTunnelIP` | ip | Three archived public prefix expressions, each AND-constrained to destination port 7844. |
| `WindowsReject` | domain | Only the archived `ipv6.microsoft.com` suffix selector. |
| `WindowsGateway` | domain | Archived delivery-optimization/connectivity/Store domain controls; no new Microsoft parents. |
| `WindowsGatewayPorts` | transport | UDP destination port 123, plus protocol-independent destination port 7680. |
| `CampusNetwork` | domain | Derived from `lists/PKU.list`, including reviewed additions such as `pku-dasys.cn` when present there. |
| `CampusServices` | domain | `CampusNetwork` + `lists/Academic.list` + `config/campus-services.json`. |
| `CampusExtraIP` | ip | Only the owner-approved extra campus destination; an early raw-address exception, never a replacement for resolving PKUIP. |
| `CampusNetworkIP` | ip | `lists/PKUIP.list` + CampusExtraIP; add/preserve `no-resolve` on every leaf for physical-campus variants. |
| `UKAI` | domain | The exact 30 existing UK inline AI exceptions, retaining their order and match types. |

The archived campus domain set is already completely represented by PKU,
Academic, and the campus-service configuration: there are **no residual domain
rules to copy**. Do not create another maintained publisher or institutional
list. An update to any of these dependencies flows into CampusServices on the
next build. `pku-dasys.cn` is maintained in PKU; rebuild this layer after source changes
rather than adding a duplicate here.

The compiler performs stable, exact deduplication in manifest source order.
It does not sort away the UK order, collapse IP ranges, widen exact hosts to
suffixes, or infer new relay patterns. In particular, `derp??.tailscale.com`
retains its original two-character wildcard semantics; it is not restricted to
two digits and is not replaced with `derp*.tailscale.com`.

Cloudflare's archived expressions are `198.41.192.0/19`,
`2606:4700:a0::/44`, and `2606:4700:a8::/44`. The last has host bits and masks to
the same effective IPv6 `/44` as the second. This one reviewed legacy spelling
is retained, not treated as a third disjoint network or widened to an aggregate.
Both runtimes' syntax checks accept it. Boundary tests compare the effective
sets and require port 7844 for both TCP and UDP. This is compatibility with the
reviewed device source, not a fresh expansion to all Cloudflare addresses.

Additional generated outputs:

- `overlays/index.json`: intended clients, kinds, reasons, placement boundaries,
  ordering/conflicts, rule counts, transitive **relative** input paths and SHA-256
  hashes, output paths, official URLs, and provider IDs. This is generated
  metadata, not another editable manifest.
- `overlays/clash/rule-providers.yaml`: HTTP provider declarations only. It has
  **no** `rules`, policies, DNS, TUN, listeners, or proxy definitions. Copy only
  the selected declarations into the private profile.

Provider IDs are `DeviceOverlay<Name>`, with a separate cache namespace
`./rule-sets/surge-rules/device-overlays/v1/<Name>.list` and a refresh interval of
86400 seconds. Common `clash/rule-providers.yaml` remains independent.

## Strict manifest contract

The version-1 root has only `version` and `overlays`. Every overlay requires:

- `name`, `kind` (`domain`, `ip`, or `transport`), `clients`, and a nonempty
  English `reason`. Supported intended clients are `surge-macos`, `surge-ios`,
  and `mihomo-windows`. Export format availability is not automatic authorization
  to enable an overlay on every client; UKAI is currently intended for the UK
  macOS profile only.
- `placement`, `before`, and `conflicts`. Placement is one of `before-common`,
  `after-reject`, or `uk-ai-exceptions`. `before` references must agree with
  manifest order; conflicts must be symmetric.
- An ordered, nonempty `sources` array using the following tagged forms.

| Source type | Required fields besides `type` | Contract |
|---|---|---|
| `overlay` | `name` | Same-kind composition dependency; unknown references and cycles fail. Does not imply another runtime call. |
| `common` | `path` | Only `lists/PKU.list`, `lists/Academic.list`, or `lists/PKUIP.list`, with the corresponding domain/IP kind. |
| `campus-services` | `path` | Only `config/campus-services.json`; its version/family/evidence/suffix schema is checked. |
| `file` | `path`, `public_suffixes`, `cidrs`, `ports` | A policy-free file directly under `overlays/sources/`, bounded by explicitly reviewed public namespaces, exact CIDR expressions and destination ports. |

`public_suffixes` normally bounds a namespace: a selector must equal that scope
or end in `.` plus the scope. A scope containing `*` or `?` instead authorizes
**only that exact wildcard expression**, as needed for the UK regional AI API
rule. It does not authorize every Google API host. CIDR and port scope lists
contain exact reviewed values, not inferred ownership. A port-constrained IP
source must retain the conjunction, not a naked CIDR.

Duplicate JSON keys, duplicate names/source rules, missing/unknown fields,
unknown source types, unsupported rules, policies embedded in sources, mixed
kinds, path traversal, absolute paths, symlinks, empty sources and unreferenced
source files fail closed. Only DOMAIN/DOMAIN-SUFFIX/DOMAIN-WILDCARD, destination
CIDRs, destination ports, and the two explicitly supported port conjunction
shapes are portable here. No source-IP, process, arbitrary logical expression,
GEOIP/ASN, ruleset include, keyword, or protocol-only fallback is accepted.
Private/local namespaces, individual `ts.net` descendants, and non-global CIDRs
other than the three documented exceptions are rejected.

The curated public scopes are reviewed admission boundaries, not a heuristic
that can determine who owns every internet hostname. Review any manifest scope
change as a new public selector admission. PKU, Academic and campus-services
remain separately reviewed public sources; this builder must not silently
freeze them into a second allowlist. Source comments are not copied into the
generated payloads. Review the **sources and metadata too**, not just outputs,
for accidental private content before publication.

## Ordering and policy binding

First match still wins. Apply only the selected overlays; do not append this
entire catalog to every device or replace the common rule sequence with it.

1. **Before common routing:** keep the device's private guards in their existing
   positions. Select at most one of TailscaleProxy and TailscaleCampusProxy, and
   place it before TailscaleControl. Preserve the caller's website/relay policy
   and control fallback policy; their different scopes are intentional. Keep
   TailscaleNetwork/IP bound to the desktop OS path or the iOS native Tailscale
   outbound as appropriate. The Windows selectors are optional Windows-client
   controls, even when the gateway runtime is Surge on macOS. WindowsReject
   precedes WindowsGateway; neither should lose its private client guard.
2. **After common Reject:** on a confirmed physical campus egress, insert
   CampusServices and the intended campus raw-IP overlay after the Reject domain
   call and before ordinary service proxy calls. Keep every common list's relative
   order unchanged. CampusNetwork is already a subset of CampusServices; use its
   narrower scope for DNS/real-IP/bypass integration, or an earlier same-policy
   routing call only if needed. Do not add an extra different-policy call that
   steals campus service ownership. IP leaves and IP calls keep `no-resolve`, so
   early raw-address exceptions cannot initiate DNS before domain routing.
3. **Existing UK profile only:** replace its inline exception block in place,
   preserving its policy and the sequence **ModelDownloadCDN, AI, UKAI, AIIP,
   final**. Do not substitute a broad Google/Microsoft/Meta/X service list. Do not
   add the full common tree to the smaller UK profile as part of this conversion.

On a remote-campus Mac, retain the original resolving `lists/PKUIP.list` call
after RejectIP. Use only CampusExtraIP at the earlier raw-address exception.
Moving all campus ranges early, or deleting the later resolving call, would
change routing for unowned domains and pre-resolved service destinations.

`no-resolve` prevents initiating a lookup, not matching an address already
available. The overlays do not change the common v2 domain/IP resolution stage.
They also do not add `extended-matching` or configure sniffing implicitly.
Preserve existing device behavior; [the Clash contract](CLASH.md) describes the
limits of hostname inference across runtimes.

Official production URLs use `@main`:

```text
https://cdn.jsdelivr.net/gh/yhyfhgs/surge-rules@main/overlays/surge/TailscaleProxy.list
https://cdn.jsdelivr.net/gh/yhyfhgs/surge-rules@main/overlays/clash/TailscaleProxy.list
```

A neutral desktop Surge example (the policy `ExampleProxy` must be supplied by
the private profile):

```ini
RULE-SET,https://cdn.jsdelivr.net/gh/yhyfhgs/surge-rules@main/overlays/surge/TailscaleProxy.list,ExampleProxy
RULE-SET,https://cdn.jsdelivr.net/gh/yhyfhgs/surge-rules@main/overlays/surge/TailscaleControl.list,DIRECT
```

The equivalent Mihomo calls, after selecting their generated provider entries:

```yaml
rules:
  - RULE-SET,DeviceOverlayTailscaleProxy,ExampleProxy
  - RULE-SET,DeviceOverlayTailscaleControl,DIRECT
```

These are fragments, not complete configurations. A guarded gateway call needs
its private outer condition; a native iOS network call must not be replaced
with desktop DIRECT behavior. IP calls additionally retain `,no-resolve`.

## DNS and application capture are separate

The overlay lists contain **no DNS settings**. Keep DNS capture, resolver
selection, real-IP handling, OS routes, and application policy distinct:

- Capture normal desktop DNS in Surge/Mihomo while keeping independent Tailscale
  DNS acceptance disabled. Route the whole `ts.net` namespace to Quad100 with
  `ts.net` and `*.ts.net` on Surge, or `+.ts.net` on Mihomo. Do not enumerate peers
  or use Quad100 as a general public fallback. Preserve native iOS integration.
- Desktop Tailscale control/relay DNS retains its direct encrypted resolver
  mapping. A website proxy exception does not automatically require a different
  DNS resolver; preserve the existing resolver design and prevent bootstrap
  recursion. Put the scoped mappings before broader common mappings.
- Use CampusNetwork's domain rules for verified campus resolver and real-IP
  selection. Keep CampusServices' public publisher/software families on the
  chosen campus egress without inventing arbitrary shared-CDN bypass routes.
  Surge `[Host]` can use `RULE-SET:<Surge overlay URL> = server:<verified resolver>`;
  Mihomo can reference `rule-set:DeviceOverlayCampusNetwork` in its domain-based
  DNS policy. Keep these references on the same official base as routing.
- IP/port overlays cannot select a DNS upstream before resolution. Do not put
  CampusNetworkIP or CloudflareTunnelIP into a domain DNS mapping. Derive any
  TUN exclusion/real-IP settings explicitly in the private builder, not by
  copying every IP provider. Never exclude a proxy fake-IP/listener range.
- `DIRECT` still traverses the proxy runtime. Complete application bypass also
  requires correct host/IP proxy bypass and OS routes. macOS Tailscale IPv4 and
  IPv6 exclusions have different recorded behavior; preserve the
  verified device routing boundary; a static file is not an OS-route proof.

Resolver mappings and provider refreshes are not proof of universal UDP/TCP/IPv6
DNS capture, campus entitlement, or gateway forwarding. Test on the actual
intended device without mutating policy selections during live validation.

## Build, API, and verification

From the repository root, using Python 3.9 or newer and the standard library:

```bash
python3 tests/device_overlays_test.py
python3 tools/device_overlays.py
python3 tools/device_overlays.py --check
python3 tools/device_overlays.py --check --native
```

`--check` is deterministic and read-only: no timestamps or absolute input paths
are embedded, and identical rebuilds preserve output mtimes. Exit codes are 0
for success/current outputs, 1 for drift, and 2 for input/native validation
failure. Build validates every input before replacing changed files atomically.
Observed source changes during rendering fail for retry. Unexpected generated
files are reported and preserved, never silently deleted as concurrent work.

The importable `tools/device_overlays.py` API (put `tools` on the Python module
path, as the existing builders do) is:

| Function | Result / boundary |
|---|---|
| `load_manifest(root=ROOT)` | Strictly validated entry dictionaries in manifest order. |
| `compose(root=ROOT)` | `(entries, rules_by_name, transitive_input_paths_by_name)`; rules are policy-free Surge strings. |
| `build(root=ROOT)` | Pure mapping `{repository_relative_output_path: text}` for all 34 artifacts. No installation. |
| `ordered_selection(names, client, root=ROOT)` | Selected entries in manifest order; validates intended clients and mutually exclusive alternatives. Does not insert common rules or select composition dependencies as extra calls. |
| `provider_name(name)` | `DeviceOverlay<Name>`. |
| `render_call(name, policy, mihomo=False, root=ROOT)` | A single caller-policy RULE-SET call using the official URL or provider ID; IP calls include `no-resolve`. Does not apply private guards or placement. |
| `drift(artifacts, root=ROOT)` | `(changed_or_missing_paths, unexpected_paths)`, without writes. |
| `write_artifacts(artifacts, root=ROOT)` | Replace only changed expected output files. |
| `validate_native(artifacts)` | Require offline Surge and Mihomo checks; returns the overlay count. |

The native checker uses temporary **Surge `[Ruleset Name]` sections**, so
`surge-cli --check` actually parses every list body; checking a profile containing
only remote references would not prove that. A deliberately invalid inline rule
must fail as a negative control. No active profile is installed or reloaded.

Mihomo `-t` checks the local text-classical provider declarations, but **does not
load their bodies**. The checker therefore also expands the exact generated
Mihomo payloads into an isolated inline-rule configuration, inserts a neutral
policy at the proper position, and tests that configuration. Its invalid inline
control must fail too. `DEST-PORT` becomes `DST-PORT`, `PROTOCOL,UDP` becomes
`NETWORK,udp`, nested parentheses and native `no-resolve` are preserved. TUN and
DNS listeners remain disabled. This proves native configuration/rule syntax,
not live provider loading or traffic behavior. Native failure logs stay outside
the repository.

The regression tests cover dependency propagation, stable union/order, intended
client selection, no policy/process/source guards or QUIC-block payloads,
private namespace/address rejection, relative paths/symlinks, non-exported
comments, strict schema failures, exact UK selectors, and independent positive
and negative port/IP/wildcard witnesses. They use only public inputs and neutral
temporary fixtures, never private profiles.

## Publication and deployment boundary

Rebuild after any dependency change, including PKU/Academic/campus-services.
Review the public source/manifest/output diff and run the common
[maintenance validation workflow](MAINTENANCE.md#validate-a-change) for the
parent routing batch. `update.sh` validates the overlays and includes all 34
generated artifacts in its publication/CDN gate. When preserving unrelated
uncommitted work, stage the reviewed release paths explicitly and use
`SURGE_RELEASE_STAGED_ONLY=1`; the publisher checks staged source/output bytes
against the validated working files before committing. It never uploads private
profiles. Do not use the default `git add -A` mode on an unreviewed tree.

Do not point deployed clients at new `@main` files until the parent has published
and verified their exact bytes. Local build/check success is
**VALIDATED_NOT_PUBLISHED**, not a release or proof of client refresh. The parent
handles publication gating, private configuration integration, native checks of
complete candidates, and installation. This tool does none of those actions.
