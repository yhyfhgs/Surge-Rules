# Sources

This register records upstream material used in the distributed rules and test
criteria. Source revisions and licenses below describe the recorded inputs;
curated lists may differ from upstream routing decisions. Retired script/module
development references remain in Git history.

## FINAL review and portable overlays (2026-10-27)

The 29 new common service rules use current first-party pages and explicit
application links, not an aggregate import. Scholarly publication/repository and
research identifier services use Academic; independent AI applications use AI.
Manus and Microsoft news gain exact hosts only. Generic components, tenant
boundaries, unidentified infrastructure and raw shared-cloud IPs remain unassigned.
Observed page hashes and narrow decisions are recorded in
`sources.lock.json:final_monitor_review_20261027`; these are mutable-page
observations, not replayable list imports or authenticated-access claims.

| Owner | Accepted rule | First-party evidence |
|---|---|---|
| Academic | `DOMAIN-SUFFIX,aaai.org` | https://aaai.org/<br>https://ojs.aaai.org/ |
| Academic | `DOMAIN-SUFFIX,aeaweb.org` | https://aeaweb.org/ |
| Academic | `DOMAIN-SUFFIX,biorxiv.org` | https://biorxiv.org/ |
| Academic | `DOMAIN-SUFFIX,computer.org` | https://computer.org/ |
| Academic | `DOMAIN-SUFFIX,connectedpapers.com` | https://connectedpapers.com/ |
| Academic | `DOMAIN-SUFFIX,litmaps.com` | https://litmaps.com/ |
| Academic | `DOMAIN-SUFFIX,medrxiv.org` | https://medrxiv.org/ |
| Academic | `DOMAIN-SUFFIX,nber.org` | https://nber.org/ |
| Academic | `DOMAIN-SUFFIX,orcid.org` | https://info.orcid.org/<br>https://orcid.org/ |
| Academic | `DOMAIN-SUFFIX,osf.io` | https://osf.io/<br>https://psyarxiv.com/ |
| Academic | `DOMAIN-SUFFIX,peerj.com` | https://peerj.com/ |
| Academic | `DOMAIN-SUFFIX,physiology.org` | https://physiology.org/ |
| Academic | `DOMAIN-SUFFIX,psyarxiv.com` | https://psyarxiv.com/<br>https://osf.io/ |
| Academic | `DOMAIN-SUFFIX,researchsquare.com` | https://researchsquare.com/ |
| Academic | `DOMAIN-SUFFIX,taylorandfrancis.com` | https://taylorandfrancis.com/ |
| Academic | `DOMAIN-SUFFIX,zenodo.org` | https://zenodo.org/<br>https://developers.zenodo.org/ |
| AI | `DOMAIN-SUFFIX,braintrust.dev` | https://braintrust.dev/ |
| AI | `DOMAIN-SUFFIX,consensus.app` | https://consensus.app/ |
| AI | `DOMAIN-SUFFIX,elicit.com` | https://elicit.com/ |
| AI | `DOMAIN-SUFFIX,researchrabbit.ai` | https://researchrabbit.ai/ |
| AI | `DOMAIN-SUFFIX,scite.ai` | https://scite.ai/ |
| AI | `DOMAIN,open.manus.ai` | https://manus.ai/ |
| ProxyGFW | `DOMAIN-SUFFIX,astral.sh` | https://astral.sh/ |
| ProxyGFW | `DOMAIN-SUFFIX,basecamp.com` | https://basecamp.com/ |
| ProxyGFW | `DOMAIN-SUFFIX,codecov.io` | https://codecov.io/ |
| ProxyGFW | `DOMAIN-SUFFIX,eclipse.org` | https://eclipse.org/ |
| ProxyGFW | `DOMAIN-SUFFIX,postgresql.org` | https://postgresql.org/ |
| ProxyGFW | `DOMAIN-SUFFIX,pytest.org` | https://pytest.org/ |
| Microsoft | `DOMAIN,news.microsoft.com` | https://news.microsoft.com/ |

The owner's existing `pku-dasys.cn` selector moves into PKU. Optional public
device overlays derive PKU, Academic and `config/campus-services.json`, and keep
portable Tailscale/Windows/tunnel/UK selectors separate from global ownership.
The explicit campus destination is owner-requested, not an inferred cloud range.
See [overlay composition and privacy boundaries](docs/DEVICE-OVERLAYS.md).

## Rule inputs

| Source | Recorded revision | Recorded license | Use |
|---|---|---|---|
| [blackmatrix7/ios_rule_script](https://github.com/blackmatrix7/ios_rule_script) | Initial material `65e8adf` (2026-08-28); current ChinaIP pin in `sources.lock.json` | GPL-2.0; upstream README also restricts public-account/self-media reposting | ChinaMaxNoIP → ChinaDomain; ChinaIPs IPv4/IPv6 → ChinaIP. Curated LAN, Apple, games/downloads, proxy, Telegram, TikTok, domestic vendor/media and Reject layers. Service lists supplied comparison evidence. |
| [SukkaW/Surge](https://github.com/SukkaW/Surge) / [ruleset.skk.moe](https://ruleset.skk.moe/) | Early URL imports were not revision-pinned; review inputs in `routing_review` | AGPL-3.0 | Initial Domestic, DownloadCDN, Streaming, AI, AppleCN, MicrosoftCN and ChinaIP material; advertising entries curated into Reject. Later CDN/download host additions are difference-based. |
| [Repcz/Tool](https://github.com/Repcz/Tool) | Branch `X`; early URL imports were not revision-pinned | MIT | Initial service/download lists, later merged into YouTube, Twitter, TikTok, Streaming, MicrosoftCN and DownloadCDN. Subsequent OneDrive ownership follows the evidence below. |
| [Loyalsoldier/surge-rules](https://github.com/Loyalsoldier/surge-rules) | Branch `release`; early URL imports were not revision-pinned | GPL-3.0 | `private.txt` and `icloud.txt` contributed to PrivateLAN and AppleCN. |
| [VPSDance/ai-proxy-rules](https://github.com/VPSDance/ai-proxy-rules) | Early imports unpinned; later review inputs in `ai_review` | MIT | Initial AI material and later provider review. |
| [VirgilClyne/GetSomeFries](https://github.com/VirgilClyne/GetSomeFries) | `b4aa767` (commit 2026-05-06; reviewed 2026-09-13) | GPL-3.0 | Difference-based additions from `ruleset/HTTPDNS.Block.list` to Reject's HTTPDNS/private DoH layer. |
| [Semporia/TikTok-Unlock](https://github.com/Semporia/TikTok-Unlock) | `557dc2b` (2026-08-29) | No license recorded | TikTok list comparison only; no whole-table import. |
| [v2fly/domain-list-community](https://github.com/v2fly/domain-list-community) | `bcea254` (commit 2026-09-25; reviewed 2026-09-26) | MIT | Difference-based vendor additions to Meta, Payment, Google, AI and Domestic after registration or NS checks; no whole-category import. |

Old ignored clones under `reference/` were removed on 2026-09-01. The recorded
revisions identify the reviewed material; the clones are not build inputs.
Copyright remains with the respective authors. This repository has no declared
license of its own.

## Runtime and test criteria

| Source | Role | Recorded license / version |
|---|---|---|
| [Loyalsoldier/geoip](https://github.com/Loyalsoldier/geoip) | External `Country.mmdb` used by the local Surge profile; not distributed here | CC-BY-SA-4.0; rolling `release` |
| [Surge manual](https://manual.nssurge.com/) | Rule-set, matching and resolver semantics | Copyright Surge Networks; no local copy distributed |
| [Public Suffix List](https://publicsuffix.org/list/public_suffix_list.dat) | Offline A10 registration-boundary criteria, ICANN and PRIVATE sections | MPL-2.0; locked version/hash in `tests/data/SNAPSHOTS.json` |
| [IANA TLD list](https://data.iana.org/TLD/tlds-alpha-by-domain.txt) | Offline A10 valid-TLD criteria | IANA public data; locked version/hash in `tests/data/SNAPSHOTS.json` |

PSL and IANA snapshots belong only to tests, never to `lists/`. Their refresh
procedure and byte hashes are in [SNAPSHOTS.json](tests/data/SNAPSHOTS.json).
Analyze the Country/ASN databases actually used by Surge. The offline engine
uses real MMDB records for GEOIP/ASN and requires explicit address/DNS
observations; missing observations are incomplete results, not invented matches.

## Reproducibility

[sources.lock.json](sources.lock.json) and the locked fetch/rebuild tools define
reproducibility. The `blackmatrix7_china_ip` lock entry is authoritative for the
current revision, input SHA-256, transforms, exclusions and expected address-set
digests. ChinaDomain's additive refreshes (2026-09-02, and 2026-09-26 from
blackmatrix7 `9ff3629c`) remain `observed`; its guarded shadow workflow has not
established a complete rebuild. Other
curated lists are `unpinned`. This register does not promise byte-for-byte
reconstruction of every distribution file.

## Decision evidence and review inputs

- **2026-09-07, suffix ownership:** Google API tenant coverage was an explicit
  user decision; Microsoft suffix coverage used official endpoint guidance.
  The [current decisions](docs/DECISIONS.md#google-and-session-ownership) retain
  this scope and link the historical records. Microsoft's current priority and
  narrowed service parents follow v2, not the earlier fallback-list design.
- **2026-09-07, AI review:** VPSDance `cc1d596`, blackmatrix7 `5f06cac` and SukkaW
  `81632eb` supplied 18 revision-addressed files verified by the locked fetcher.
  `ai_review.inputs` holds full revisions, SHA-256 and sizes. The inputs are
  pinned; the destination lists remain curated. Official Alibaba regional API
  and TRAE endpoint evidence informed the splits. See the retained
  [AI decisions and omissions](docs/DECISIONS.md#ai-ownership-and-regional-exceptions).
- **2026-09-12, OneDrive:** Microsoft's [consumer endpoints](https://learn.microsoft.com/en-us/sharepoint/required-urls-and-ports)
  and [Microsoft 365 endpoints](https://learn.microsoft.com/en-us/microsoft-365/enterprise/urls-and-ip-address-ranges?view=o365-worldwide)
  informed ownership. `onedrive_review` records retrieval dates and observed
  HTML hashes, not immutable rule inputs. The direct trial failed and was
  superseded by [Microsoft proxy routing](docs/DECISIONS.md#microsoft-and-onedrive).
  Connectivity evidence is separate from routing-policy validation; no upstream
  rules or IP allocation data changed.


## 2026-09-13 domain/IP v2 review

The review used 371 accessible immutable inputs. Forty-one Sukka distribution
inputs were unavailable and were not counted as refreshed; the 2026-09-26
refresh below re-pinned them. Changed active bytes were
re-fetched with `fetch_locked.py`; upstream metadata and operational rule changes
are distinguished in the [current IP decisions](docs/DECISIONS.md#ip-ownership-and-guarded-admission)
and the linked immutable v2 evidence.

The latest selected Sukka source adds `boxcloud.com`, `dl.gl-inet.com` and
`thumb.wikimedia.org`. Box's existing service owner receives its file namespace;
the explicit firmware host enters DownloadCDN; Wikimedia's existing owner
already covers the image host. New Loyalsoldier reject candidates do not enter
Reject merely because an aggregate source lists them.

Current [Telegram CIDRs](https://core.telegram.org/resources/cidr.txt) define
TelegramIP's exact address set, plus one RDAP-verified range readmitted on
2026-09-26 (below). Netflix's [network documentation](https://openconnect.zendesk.com/hc/en-us/articles/360035533071-Network-configuration)
identifies AS2906/40027/55095. Fresh ARIN/RIPE/APNIC network records support the
specific retained/narrowed first-party scopes in `config/ip-review-exclusions.json`;
RDAP entity ranges are never extrapolated to an entire legacy prefix. Quarantine
is not a claim of expiry. No source list contains private proxy exit mappings.

## 2026-09-26 upstream refresh

Thirteen branch heads across eleven repositories were compared with the 412
earlier inputs: 339 were byte-identical, 66 changed and 7 had no new revision.
The SukkaLab distribution inputs are available again, and Sukka's new
`domestic_cdn` source files were added. `routing_review.inputs` now pins all 415
reviewed files at those heads; `fetch_locked.py --network` verified every SHA-256.
Changed files were compared at rule level before any list edit.

- **ChinaIP:** blackmatrix7 `9ff3629c` is the locked input. Its four removed
  ranges carry foreign RDAP registrations. Two new ranges registered to
  Uniregistry/Tucows (US/CA) are held back in the lock's review holdback step.
- **ChinaDomain:** the additions-only workflow used the same revision. Only
  positive KEEP verdicts were admitted; a P10 carrier pin and a PSL boundary are
  not admission evidence.
- **Vendors and services:** v2fly `6fe5416`, `b4a85ba`, `e5c669c`, `12b6e93`
  and `5ab6d48` added first-party domains that the lists absorb after RDAP or
  shared-NS checks. VPSDance `4188a51` added `llamameta.net`; meta-llama's
  `llama-models` identifies it as the model-weight download host.
- **Blocking and regions:** gfwlist `61652e3`, `75a147d` and `74b55d2`, mirrored
  by blackmatrix7 `Proxy_All` and Loyalsoldier `gfw.txt`, supplied three
  additions. `note.com` belongs to the Japan owner instead of ProxyGFW.
- **CDN and download:** Sukka's new exact CDN/download hosts enter DownloadCDN
  unless an existing owner covers them or they are embeddable SaaS components.
  Sukka `0e4b52b` removed `tripcdn.com` from its global CDN set; its GSLB returns
  China Mobile addresses to domestic resolvers.
- **Evidence only:** Loyalsoldier, hagezi and Sukka aggregate reject deltas,
  v2fly/MetaCubeX `geolocation-cn` changes and Sukka's `domestic_cdn` split
  changed no list. Official Telegram CIDRs still equal TelegramIP.

## 2026-09-26 FINAL monitor review

Candidates came from private connection metadata recorded outside this
repository; no upstream rule list was imported. Ownership evidence consisted of
RDAP registrar and nameserver records, the RIPE record for `95.161.64.0/20`,
the Surge application's Sparkle feed URL (`sgupd.com`) and page titles.
TelegramIP now extends the official CIDR set by that one range. Accepted
scope and exclusions are in the
[FINAL monitor review](docs/DECISIONS.md#final-monitor-review).

## 2026-10-09 list-only upstream refresh

All 415 review inputs were fetched at 13 current branch heads across 11
repositories and independently re-fetched with `fetch_locked.py` verification:
342 byte-identical, 57 rule-content changes, 13 order-only changes and 3
code/documentation changes. No tracked path was unavailable. Current immutable
revisions and hashes are in `routing_review.inputs`; the older `ai_review`
remains historical evidence, not the latest AI snapshot.

- **AI:** VPSDance `49d0081c`, blackmatrix7 `036c097e`, Sukka `1c454d54` and
  v2fly `3e4cb549` supplied comparison evidence. First-party Claude, Devin,
  OpenClaw, ACP, Dola, OpenSpec, Plannotator, Mozilla.ai, NoteGPT, NovelAI and
  DreamGen pages support eleven previously missing AI service/tooling domains.
  The live Muse site identifies Meta; its cached search copy still describes
  the former video product and was not used for ownership. Limitless's own
  announcement supports moving its existing suffix from AI to Meta.
- **Payment:** Paddle's hosted-checkout documentation, Square's payment-link
  response and Nuvei's checkout/Web SDK documentation support new checkout
  endpoints. Nuvei's `cdn.safecharge.com` leaves DownloadCDN and is absorbed by
  Payment's `safecharge.com`. Explicitly documented Paddle, Square, Adyen and
  Wise sandbox endpoints are included; no production Adyen region is inferred.
  MEGA's official-domain register identifies `megapay.nz` as its own checkout,
  which follows MEGA's existing DownloadCDN account/session family rather than
  introducing a Payment or ProxyGFW split.
- **Residual/download:** blackmatrix7 and Loyalsoldier's current blocking lists
  supply 38 unowned domain additions; existing Qobuz and service owners remain.
  Six exact CDN/download hosts come from Sukka, with Repcz corroborating five.
  Shared measurement, embedded SaaS, Sony account assets and already-owned AI
  resources do not become download or reject entries merely by aggregation.
- **ChinaIP:** the new locked blackmatrix7 input is `036c097e`. Fresh APNIC
  registration and complete actual Country-MMDB coverage support two IPv4 `/23`s
  and one IPv6 `/32`. Newly introduced Vietnam and Greek-registered coverage is
  held back; two pre-existing HK ranges removed upstream are explicitly retained
  with fresh RDAP evidence and unchanged hard exclusions. This produces exactly
  three new rules, not the thousands suggested by the upstream text diff.
- **ChinaDomain:** the additions-only shadow run resolved 229/396 candidates
  (57.8%), below the unchanged 70% gate. No output or state change was adopted.
  The layer remains at its previous admitted content; upstream removals are not
  evidence of expiry. No new Reject, regional, AIIP or TelegramIP rule was needed.
  Telegram's freshly fetched official CIDRs plus the reviewed `/20` exactly
  equal the existing list.

`sources.lock.json:routing_refresh_20261009` records first-party URLs, observed
response hashes, IP registration evidence, withheld expansions and the failed
ChinaDomain admission gate. These mutable reference pages are not claimed to be
immutable build inputs. No configuration, provider manifest or production URL
changes belong to this refresh.
