# 更新记录

当前约定见 [现行决策](docs/DECISIONS.md)，操作流程见 [维护手册](docs/MAINTENANCE.md)。
历史数字只代表对应批次，当前数量以检查输出为准。

## [2026-11-21·机器层刷新] ChinaIP/ChinaDomain 上游刷新与 IPv6 字面地址守卫覆盖层

- ChinaIP 锁定输入升至 blackmatrix7 `0b6897dc`（2026-10-27）。经既有变换后，上游相对现表 +364/−12。只有 5 段同时被 RDAP 登记和真实 Country MMDB 完整区间确认为 CN 而接收：45.251.248.0/23、160.202.210.0/23、2402:7da0::/32、2402:7e20::/32、2402:7ee0::/32。其余 359 段多为境内企业的海外云网段（MMDB 为美国、新加坡、香港、德国、日本等），按“只暂扣新增覆盖”处理为 374 条暂扣，直连它们会把这些地区托管的网站绕出代理。按新鲜 RDAP 保留 8.210.152.255/32、183.91.63.0/24（香港）与 202.92.8.0/21（广东电信），2026-10-09 决定保留的 /48 不变；外国登记的上游删除项及无 CN 证据者随上游移出。净变化 +5/−8，共 11,063 条。
- ChinaDomain 同版本只增不删：影子运行 590/821（71.9%）、正式运行 592/821（72.1%），均过不变的 70% 闸门，收录 348 条 KEEP；公共后缀 in.th 继续暂扣；无删除，不推进迟滞。53 张公共表共 141,192 条。
- 新增无策略可选覆盖层 IPv6Any（整个 IPv6 空间，生成 Surge/Mihomo 两份）。校验器把 `::/0` 登记为第四个非全局例外，只作私有配置里“拒绝局域网、校园和国内以外的 IPv6 字面目的地”的正向条件，不成为路由属主，不改变 53 表顺序。覆盖层 17 个，产物 36 个。私有配置中的守卫规则、双栈别名和节点信息不入库。
- 验证：覆盖层回归 41 项、Surge/Mihomo 规则正文原生检查及反例通过；场景 397 组 5,595 条断言（含 2,401 条 DNS）全过，新增 3 组见证在旧规则上有 16 条失败，说明覆盖了本次改动；按维护流程在仓库外生成的标准合同候选通过渲染一致性、原生语法和 Clash 合同（53 provider、141,192 条、86 归属见证）。发布脚本会在提交前对最终内容重跑全部闸门。
- 发布：`02dd50c` **PUBLISHED_AND_VERIFIED**。发布脚本在提交前对最终内容重跑全部闸门：覆盖层回归与原生检查、引擎自检 55/55、真实 Country/ASN MMDB 关系分析（无遮蔽、无顺序不安全拆分）、静态审计 P0/P1/P2 为 0（保留 3 项既有 P3）、场景 5,595 条、Clash 合同。引擎自检 R03/R04/R06 按 2026-11-15 家宽 A 退役后的拓扑改为家宽 B。8 个变更分发文件全部 purge 后复验一致；IPv6Any 两份、ChinaIP、ChinaDomain 的 CDN 字节与本地一致。本机与 Mac mini 已加载新覆盖层，IPv6 字面目的地在握手阶段被拒绝。


- 新增 29 条有第一方证据的服务域名：Academic 16、AI 6、ProxyGFW 6、Microsoft 1；另将既有 `pku-dasys.cn` 纳入 PKU。共用云裸 IP、通用追踪/验证码、租户父域和私有基础设施不扩张，公共顺序与策略不变。53 张公共表共 140,847 条。
- 增加 16 个可选、无策略的设备规则集，分别生成 Surge/Mihomo，含校园网络/服务、Tailscale 网站/控制/网络/DNS、Macmini 网关和英国 AI 例外。校园列表从 PKU、Academic 和校园证据配置派生，不复制维护。IP 与域名分层，端口约束及 no-resolve 保留。私有监听器权限和进程豁免不公开。
- 发布脚本纳入 34 个覆盖层产物，支持显式暂存范围并校验暂存字节与验证输入一致；既有未提交设备开发不混入此次发布。私有配置凭据不入库。
- 验证：39 项覆盖层回归、Surge/Mihomo 规则正文原生语法及反例；5,543 条全场景断言（含 2,397 条 DNS）、84 条对抗断言、真实 Country/ASN MMDB 全量关系分析、53 provider/140,847 条 Clash 同源合同通过；静态审计无 P0/P1/P2，保留 3 项 P3。公共合同使用两端点 DNS 标准候选，完整私有设备保留其四端点 DNS，未放宽检查。
- 私有七份候选经原生检查，节点工具 54 项、监控器 13 项测试通过；Macmini 以档案内服务为基准，不采用旧通用网关整份覆盖。允许 QUIC 不等于 TCP-only HTTP 出站具备 UDP；未宣称远端设备已导入、握手或校园授权成功。
- 发布状态由最终 GitHub SHA 与 CDN 字节核验裁决；详细私有流量与部署信息不随公共规则发布。

## [2026-10-09·仅更新列表] 全上游复核、AI 与支付补漏

- 严格按用户要求：不改任何配置、规则顺序、策略组、DNS 映射或 provider URL，不重建设备配置。53 张现有列表逐项复核，只改 6 张源表及对应 Clash 镜像；规则总数 140,750 → 140,817（+69/−2，净增 67）。工作区原有未提交的设备配置开发保留且不混入发布。
- 11 个仓库、13 个分支头、415 份固定输入全部重新获取并经 `fetch_locked.py` 校验。342 份字节相同；57 份规则内容变化、13 份仅顺序变化、3 份代码/文档变化；无不可取输入。锁文件仅更新本批复核与 ChinaIP 来源，保留其他未提交元数据。
- AI 新增 11 个第一方服务/工具域（含 claude.dev、DeepWiki MCP、ClawHub、Dola、ACP、Mozilla.ai）；Muse 加入 Meta，Limitless 从 AI 移到 Meta。Google/Microsoft 的新增参考子域已被本属主覆盖，不重复抄入 AI；模型下载和国内/国际区域例外不变。
- Payment 新增 8 条：Paddle 默认收银台、Square 短链接和精确 checkout 主机、Nuvei safecharge 会话，以及文档明确的 Paddle/Square/Adyen/Wise 沙箱。`cdn.safecharge.com` 从 DownloadCDN 删除，由 Payment 父域承接。Stripe/PayPal 已有生产网关保持，未引入品牌关键词、支付租户父域、通用验证码或 Stripe 本地读卡器域。
- ProxyGFW 收录阻断参考中无专属属主的 38 个域。DownloadCDN 新增 6 个精确 CDN/下载主机，另补 MEGA 自有结算 `megapay.nz`，跟随已有 MEGA 账户/API 全域属主，不拆成 Payment/Proxy。通用 RUM、嵌入组件和 Sony 账户静态资源暂不采纳；已有 AI 资源仍归 AI。聚合 Reject 增量不直接导入。
- ChinaIP 按新 pin `036c097e` 重建，仅接收 APNIC 与实际 MMDB 完整区间均支持 CN 的 `43.241.100.0/23`、`163.52.246.0/23`、`2402:7820::/32`。暂扣 VN/GR 登记的新覆盖；原有 HK 两段按新 RDAP 证据显式保留；所有硬排除和输出参数不变。Telegram 官方 CIDR 加已复核 /20 与现表完全相同；Anthropic 新参考 ASN 已在 AIIP。
- ChinaDomain 只增不删 shadow：229/396 可解析（57.8%），未达 70% 闸门，整表不动，不采用部分结果、不降低门槛、不推进删除迟滞。后续需重新通过护栏才能刷新此层。
- 验证：5,388 条场景断言全过（388 场景、2,761 请求，含 2,345 条 DNS）；新增 13 场景/294 断言在旧规则上有 89 条失败。84 条对抗断言通过；原生 Surge、排序、真实 MMDB 关系分析、静态审计和全量 Clash 同源检查执行；静态审计保留 3 项既有 P3，无 P0/P1/P2。发布脚本会在提交前对最终内容重跑全部闸门。
- 设备配置的四端点 DNS 池与旧公共 Clash 合同的两端点模板不同，直接对设备候选运行该合同会失败；未修改配置或放宽测试。公共合同按维护流程在仓库外生成标准候选，53 provider、140,817 规则与 86 归属见证通过；原设备候选另通过完整场景和原生语法。实际账户登录、支付/3DS 和远端设备刷新不在这些静态验证之内。
- 发布：`52753b133521899bdf9026e41d70294bb219bce4` **PUBLISHED_AND_VERIFIED**。发布脚本在提交前对最终内容重跑全部闸门并校验远端 SHA。虽然预检 12 个分发文件已一致，仍显式 purge 全部 12 个变更路径，CF/FY 均确认；`@main` 和固定提交各 107/107 分发文件 SHA-256 一致，GitHub 12/12 变更文件一致。
- 本机仅刷新六个现有外部规则资源，不切换/重载配置或策略组；69/69 新增规则的原生实际匹配均落到预期源表。38 个配置相关文件的 SHA-256 与操作前完全相同。生产仍用原有 `@main` URL，其他使用者下次成功刷新资源即可获取，不需要替换配置；固定旧提交及旧混合列表客户端不自动迁移。未验证每台远端设备或真实登录/支付。

## [2026-10-05·DNS 接管与业务绕过纠正]

- 后续按用户纠正：撤销下面记录的“实际 tailnet 后缀”收窄，所有 `ts.net` 域名统一交给 Quad100。Surge 生成 `ts.net` / `*.ts.net`，Mihomo 生成 `+.ts.net`；额外配置只能扩展专用域，不能缩小 `ts.net` 覆盖，重复子域自动合并。三份 Surge 均显式生成该 DNS 映射，iOS 保留原生 Tailscale 出站。21 项回归（含多个 tailnet、多层子域与相似域名反例）、五份原生检查及重建一致性通过；五份产物已同步，本机生效配置与真实 MagicDNS 查询验证通过。状态 **VALIDATED_NOT_PUBLISHED**。

- 按用户澄清，将 DNS 接管、按域名选择专用上游、业务流量绕过分开处理。修复生成器删除旧配置中 `hijack-dns = *:53` 的问题；真实 tailnet 后缀统一生成 Quad100 映射、真实 IP 返回和系统代理排除，补齐自定义后缀的子域匹配。
- 私有清单校园 DNS 从 `system` 改为北大官方列出的 `162.105.129.122`、`162.105.129.88`。校园 Mac mini 补齐 PKUIP 与显式额外网段的 `tun-excluded-routes`、域名/IP `skip-proxy`、真实 IP 返回；Windows 补齐额外校园域名的真实 IP 过滤。禁止校园排除与 Tailscale 或 Fake IP 地址池重叠。期刊及公网 CDN 保持校园 DIRECT，不把 CDN 网段扩大为绕过。
- 验证：新增回归在旧逻辑中因缺失 hijack-dns 失败；修正后 20 项设备回归、五份原生语法检查及重建字节一致性通过。5,094 条公共场景断言（含 2,232 条 DNS）全过；实际 MMDB 关系检查无冲突；静态审计 P0/P1/P2 为 0，保留 3 项既有 P3；53 表、140,750 条规则和 Clash 合同一致。节点、组成员及证书保留。
- 五份私有产物已同步，本机 Surge 已重载；生效配置与 DNS trace 确认国内/海外加密 DNS、实际 tailnet→Quad100，客户端 MagicDNS 查询返回真实 Tailscale IPv4。UDP 53 探测返回 Fake IP，但 TCP 53 返回公网真实 IP，不能报告“所有 DNS 已接管”。当前 Quad100/实际节点 IPv4 路由指向 Tailscale；IPv6 路由探测未取得可用接口，不沿用历史成功记录作本次验收。
- 状态 **VALIDATED_NOT_PUBLISHED**。公共列表/CDN 未改；其他设备未远程部署，校园 DNS 可达性、机构授权和网关转发仍待目标机验收。

## [2026-10-05·五类设备配置] 统一私有配置源与校园分流变体

- 加密 DNS 扩容：按用户要求新增 DoT，五份私有配置的国内/海外解析池分别从 2 个 DoH 扩为 2 个 DoH + 2 个 DoT，由 `config/device-dns.json` 统一维护。桌面 Tailscale 控制域名增加国内直连加密 DNS 映射；保留 MagicDNS、局域网及校园专用解析。八个端点均通过本机证书校验及 DNS 报文查询；16 项设备回归、五份原生检查、重建一致性通过。公共规则候选 5,094 条场景（含 2,232 条 DNS 断言）全过；设备覆盖中的既有 Tailscale DIRECT 例外由设备测试验证，不套用公共 Proxy/下载预期。本机重载后实际观察到国内 DoT、海外 DoH 和 Quad100 分流，双栈与完整域名 SSH 握手仍正常。状态 **VALIDATED_NOT_PUBLISHED**；其他设备产物已更新，未远程部署。

- SSH 实测修正：Mac/Mac mini 生成器不再把 Tailscale IPv4 网段与额外 IPv4 子网写入 `tun-excluded-routes`，并清理底稿中的同类残留。本机原排除项生成了物理网关路由，抢走 Tailscale IPv4；保留现有 IPv6 排除，因为实测同时移除会使 IPv6 落入 Surge 默认路由。14 项回归、五份原生语法检查及重建一致性验证通过；本机重载后 IPv4、IPv6、完整 MagicDNS 名均返回远端 SSH 握手。手机与两个 Windows 配置字节不变；Mac mini 文件已更新但未远程部署。原 SSH 别名的子网目标仍超时，未验证登录认证。状态 **VALIDATED_NOT_PUBLISHED**，公共列表/CDN 未改。

- 节点换址复核：修复导入器只清理当前参考端点、遗漏其他参考中历史端点的问题。跨所有参考收集历史地址后统一清理绕行设置；现有私有清单同步移除已退休端点残留。13 项设备回归（含旧移动端地址残留到新桌面绕行的用例）及五份原生语法检查通过；真实节点和 IP 仅保留在私有清单，不写入公开记录。

- 后续 DNS 裁决：桌面 Tailscale 关闭 DNS 接管（`accept-dns=false`），普通 DNS 统一由 Surge/Mihomo 管理，只有 MagicDNS 定向查询 Quad100；校园 DNS 保持校园上游。新增手动执行的 macOS/Windows 开关脚本及生成元数据，明确 FQDN 与系统搜索后缀的区别。更新后 12 项设备回归及五份原生语法检查通过；开关脚本未在真实目标机执行。

- 按用户确认：本机 Mac、手机、普通 Windows、校园 Windows、校园 Mac mini 网关分别生成；两个校园设备实际位于校内，Mac mini 使用与本机相同的参考配置。
- 新增私有配置生成器：节点地址与组成员单一维护，Surge/Clash 保留各自协议参数；私有材料和输出强制在公开仓库外。手机原生 Tailscale 与桌面 Tailscale 放行分开生成；传输进程例外限定白名单且必须记录理由，不放宽公共列表禁令。
- 校园变体在 Reject 后添加 PKU、Academic 与有来源的期刊、软件服务直连层，保留校园 DNS；Windows 额外排除校园 IP 的 TUN 接管。Clash Verge Rev 的系统代理关闭、TUN 开启偏好独立提供，严格路由关闭以兼容独立 Tailscale。
- 验证：三份 Surge 和两份 Mihomo 原生语法检查通过；11 项设备回归、5,094 条公共场景断言（含 2,232 条 DNS 断言）、84 条对抗断言全过；53 表、140,750 条源规则与 Clash 一致；真实 Country/ASN MMDB 分析无遮蔽、顺序冲突或拓扑循环；静态审计无 P0/P1/P2，保留 3 个既有 P3。再生成逐字节一致，原有节点协议参数及证书保留检查通过。
- 状态：**VALIDATED_NOT_PUBLISHED**。未改公共分流源或 CDN 产物，未切换/重载活动配置；手机、Windows、Mac mini 上的真实校园识别与授权访问待手动分发后验收。

## [2026-09-28·自有站点直连] fhxgs.cc 整域并入 Domestic

- 用户裁决：自有站点 `fhxgs.cc` 整域走直连，在 Domestic 新增 `DOMAIN-SUFFIX,fhxgs.cc`。此前它没有归属、落 FINAL。经代理出口访问新建子域 `film.confluo.fhxgs.cc` 时，出口侧解析器持续返回 DNS Failed；公共解析（Google、Cloudflare、AliDNS、DNSPod）均能正确解析，问题只在出口侧。
- 迁前实测：`confluo.fhxgs.cc`（Vercel）与 `film.confluo.fhxgs.cc`（Cloudflare Workers 自定义域）经 Surge 的 DIRECT 策略均返回 200；国内 DoH 解析结果与权威一致。
- 验证：规则 140,749 → 140,750（+1）；候选配置与现行配置一致（Domestic 已被引用，无 DNS 映射变化）；原生语法通过；真实 MMDB 关系分析无遮蔽和顺序不安全拆分；静态审计无 P0/P1/P2（3 个既有 P3）；场景 5,094 条（新增 1 组 3 条）和其中 2,232 条 DNS 断言全过；Clash 53 表 140,750 条，合同检查通过。
- 发布：`457bdd9` **PUBLISHED_AND_VERIFIED**，2 个分发文件（lists 与 clash 的 Domestic）purge 后复验一致。本机 Surge 配置无需改动，单独刷新 Domestic 外部资源后，`fhxgs.cc`、`confluo.fhxgs.cc`、`film.confluo.fhxgs.cc` 原生匹配均落 Domestic → DIRECT；film 子域经当前规则返回 200，排障时添加的临时规则已清除。

## [2026-09-26·学术出版商直连] ProxyGFW 与 DownloadCDN 的学术出版/检索域迁入 Academic

- 用户裁决：学术出版商统一走 Academic 直连。自 ProxyGFW 迁入 11 个：arXiv、OpenReview、Semantic Scholar、Elsevier、ScienceDirect、Springer、Nature、IEEE、ACM、Science 与 sciencemag.org；自 DownloadCDN 迁入 Elsevier 内容 CDN 2 个（sciencedirectassets.com、els-cdn.com）；新增 Springer Nature 资源域 springernature.com。
- 迁前实测：18 个代表主机经 Surge 的 DIRECT 策略全部可达。用国内 DoH（迁移后的解析路径）的结果绕过 Surge 直连，TLS 校验全部通过；link.springer.com 与 www.nature.com 的国内解析为 Google Cloud 入口，证书为 `*.nature.com`，不是污染。paperswithcode.com 直连 4 次均被对端关闭，保留在 ProxyGFW。
- ChinaDomain 中的出版商（Wiley、T&F、SAGE、OUP、Cambridge、JSTOR、APS、ACS、IOP、PNAS、Scopus 等）本就直连，不重复收录；地区表中的高校保持原归属。机构订阅只在校园网内生效，校外直连使用本地运营商地址。
- 验证：规则 140,748 → 140,749（+14/−13）；真实 MMDB 关系分析无遮蔽和顺序不安全拆分；静态审计无 P0/P1/P2（3 个既有 P3）；场景 5,090 条（新增 32 条）和其中 2,232 条 DNS 断言全过；对抗测试 84/84；Clash 53 表 140,749 条，合同检查通过。学术场景放到迁移前的规则上有 15 条失败，说明断言覆盖了本次迁移。
- 同批按用户要求发布仓库指令文件统一：删除只含 `@AGENTS.md` 一行的 CLAUDE.md，AGENTS.md 去掉对它的引用。
- 发布：`f48f68a` **PUBLISHED_AND_VERIFIED**。update.sh 预检发现 6 个变更文件已是新内容，没有发出刷新，但 Surge 自己下载到的仍是旧的 ProxyGFW、Academic 和 DownloadCDN。补发这 6 个文件的 jsDelivr purge 后，Surge 缓存与发布文件逐字节一致；20 条原生见证全部通过，arXiv、OpenReview、Semantic Scholar、IEEE Xplore、Springer 和 Elsevier 在当前规则下都经 DIRECT 返回 200。

## [2026-09-26·FINAL 监控归类] 按 12 天 FINAL 实测归属 99 个目的地

- 私有 FINAL 监控在 2026-09-15～26 记录 6,766 次连接、287 个目的地（已排除 16 次受控探测），在本批之前已发布的规则下（含同日上游复核）全部仍落 FINAL。本批归属其中 99 个，覆盖 5,354 次（79.1%）。Obsidian 同步、Cloudflare MCP、Writefull 和 Gemini API 文档 MCP 等高频项都有了明确归属；逐主机用量只留在私有监控里。
- 用户裁决三项：①境外、未证实被墙、没有专属归属的第一方服务并入 ProxyGFW（15 条，含 Obsidian、Overleaf 编译产物、Zotero、Tailscale、Typora、NodeSeek 和资讯站；主机商与代理服务商站点会暴露私有基础设施，未写入公开列表）；②新建 Academic 直连表（21 条，位于 PKU 之后），用校园网 IP 访问机构订阅；③Reject 只收投放与竞价面（12 条）。测量、身份图谱、ABM 与归因类按「拦广告不拦统计」继续放行。
- 服务归属：Google +3（Gemini 文档 MCP、Colab 运行时、安全浏览 OHTTP 中继）；Microsoft +1（Clarity）；AI +13（Writefull、GPTZero 等，以及 Cloudflare MCP 与 STUN 两个精确主机）；Payment +3、SocialOthers +2、Streaming +1；DownloadCDN +2（Tectonic 宏包、Surge 更新源）。TencentCN 把 `qcloud.com` 从精确顶点升级为后缀，依据是腾讯云 IM 登录端点经代理反复失败。TelegramIP 依据客户端流量和 RIPE 登记再准入 `95.161.64.0/20`。
- 约 1,412 次连接留在 FINAL，依据既有裁决或上述隐私考虑：通用 SaaS 组件；反爬、验证码、指纹与 IP 定位组件；租户边界；裸 IP；未识别域。
- 规则 140,674 → 140,748（+75/−1），表 52 → 53，有序安全拆分父域 28 → 33（均为子项在前）。
- 验证全部通过：原生语法、渲染一致性、引擎自检 54/54；真实 MMDB 关系分析无遮蔽和顺序不安全拆分；静态审计无 P0/P1/P2（3 个既有 P3）；场景 5,058 条（新增 212 条，qcloud 的 6 条断言迁入新场景）和其中 2,216 条 DNS 断言；对抗测试 84/84；Clash 53 表 140,748 条，合同检查通过。新增场景放到旧规则上有 83 条失败，说明断言确实覆盖了本批改动。
- 发布：`6cbd13c` **PUBLISHED_AND_VERIFIED**，25 个分发文件中 2 个原本一致、23 个刷新后复验一致；另抽查 5 个关键文件的 CDN SHA-256 一致。私有 Surge 配置只新增 Academic 规则与 DNS 映射 2 行，自动重载后 53 个规则集全部刷新就绪（同时生效了同日上游复核的列表），47 条原生匹配见证落到新归属；未被任何域名表认领的 `api.segment.io` 解析后按既有美国地区 IP 规则分流。Clash 配置新增 Academic provider 与规则 8 行，生产 Clash 进程未运行。

## [2026-09-26·上游复核] 固定输入重锁、ChinaIP/ChinaDomain 刷新与厂商补录

- 检查 11 个上游仓库 13 个分支头。原 412 份固定输入中 339 份字节未变、66 份有变化、7 份版本未动；9/13 无法访问的 41 份 SukkaLab 分发文件现已可取。连同 Sukka 新增的 `domestic_cdn` 3 份，共 415 份复核输入重锁到当前版本，经 `fetch_locked.py` 逐份 SHA-256 校验通过。
- ChinaIP 按 blackmatrix7 `9ff3629c` 锁定重建：接受上游删除的 4 段（Cloud Innovation 的 US 段、China Telecom South Africa 的 ZA 段）；上游新增的 `64.96.5.0/24`、`2620:57:4004::/47` 经 ARIN RDAP 为 Uniregistry/Tucows（US/CA），列入复核暂扣。11,067 → 11,063，重建 diff 为 0。
- ChinaDomain 按同一版本只增不删：761 个新候选解析成功率 78.3%（门槛 70% 未调整），写入 371 条正向 KEEP，106,962 → 107,333。修正生成器：P10 承载集保护只防删除，不能作为新增依据；PSL 公共后缀不得新增，因此拦下 `DOMAIN-SUFFIX,in.th`；同时保留现有表头。新增 1 条回归测试。
- 厂商与服务补录（均有注册或 NS 证据）：Meta 收 `tfbnw.net`；Payment 收 `stripe.dev/.events/.global`；Google 收 `firebase.dev`；AI 收 `freebuff.com`（Codebuff 更名）；Meta 的 Llama 权重下载域 `llamameta.net` 归 ModelDownloadCDN。
- 地区与直连：gfwlist 新增的 `note.com` 属日本内容平台，连同其静态资源域 `st-note.com` 归 Japan，DownloadCDN 交还 `assets./cdn.st-note.com`；`chineseposters.net`、`quakemachinex.com` 进 ProxyGFW。Sukka 已从全局 CDN 移除 `tripcdn.com`，国内解析返回中国移动地址，改归 Domestic；Firefox 新门户探测域进 Domestic。
- DownloadCDN 收 Sukka 新增的 15 条 CDN/镜像主机，已有具体归属的主机保持原 owner；嵌入式无障碍组件 `cdn.eye-able.com` 不入下载组。手工表净增 25 条，全库 140,282 → 140,674。
- 未采用：Loyalsoldier/hagezi/Sukka 聚合拒绝列表的增量、`rs.lovable.dev`（缺用途证据）、v2fly/MetaCubeX 的 geolocation-cn 增量、作业帮从百度拆分（两者都直连，blackmatrix7 仍列在百度）、gfwlist 9/26 新增（镜像尚未同步）。TelegramIP 与官方 CIDR 完全一致，无需改动。
- 验证：52 张表形态规范；原生语法通过；真实 MMDB 全量关系分析无遮蔽、无顺序不安全拆分；静态审计无 P0/P1/P2，仅 3 个既有 P3，豁免无失效；364 场景 / 2,464 请求 / 4,852 断言通过，其中 DNS 断言 2,135 条；Clash 52 个 provider 与 140,674 条规则逐条一致，86 个归属见证通过；引擎自检 55/55、v2 回归 20/20、过期安全自检通过。
- `4632936` 已推送，状态 **PUBLISHED_AND_VERIFIED**：22 个变更分发文件经先验/刷新核验一致，另对 `@main` 与固定提交各验 105/105 个文件的 SHA-256。双端私有配置已使用 `@main`，无需改动；客户端下次更新外部资源时生效，本批未重载 Surge，也未检查生产 Clash 客户端。

## [2026-09-13·文档与目录清理] 保留现行说明，归档重复资料

- 六份分散的历史证据归并为一份现行决策，保留 OneDrive、Google、AI 和 IP 归属及未完成的实测边界；完整旧记录使用固定 Git 版本链接。
- 精简 AGENTS、CLI 指南、维护流程和旧日志；修正来源文档的旧 ChinaIP pin 说明与 MMDB 行为描述，统一正式 `@main` 使用约定。
- Profiles 的旧路由计划、Clash 历史草稿、失配验证报告和缓存移至仓库外可恢复暂存；保留当前双端配置、节点/SSH 说明、部署记录和 Backup。
- 排除 Backup 后，Markdown 27 → 15 份，79 个旧文件可恢复移出；63 个本地链接/锚点、11 个固定 Git 历史引用（9 个对象）、36 个文件/通配路径检查通过，差异与私有忽略检查通过。161 个规则/代码/锁等运行相关文件、Clash 配置及保留的节点/SSH 资料与清理前逐字节一致；双端配置未由本次清理写入，未执行规则发布。

## [2026-09-13·全局工具] 安装 Surge skill 与 CLI，补充使用文档

- 从 Surge 6.9.1（12290）应用内安装 1 个 skill、5 个文件至用户级 `~/.agents/skills/surge`，Claude 通过链接共享；4 个文件与原包逐字节一致，仅修正 UI 提示中与正文冲突的 `--raw` 建议，并补显式 `$surge` 调用。
- 将 `~/.local/bin/surge-cli` 链接到应用内官方可执行文件；签名校验通过，运行中 Core 6009001 / Controller Protocol 25。11 项帮助入口通过，有效/无效临时配置分别返回 0/1。
- Codex 在仓库和独立临时目录均发现唯一、已启用的 USER skill。新增 [安装、诊断与升级指南](docs/SURGE-CLI.md)，更新 AGENTS、README、维护和测试入口；CLAUDE 继续导入 AGENTS。文档链接、路径和差异检查通过。本批仅安装工具和更新文档，未执行规则发布。

## [2026-09-13·域名/IP 分区重构] 52 表与加密解析兜底

- 35 个原表名称保留，拆出 17 个 IP 表；域名先于 IP，各区代理/地区/直连连续。Microsoft/Games 收窄父域，保留 67 个 OneDrive 会话正例和下载例外。
- 规则 142,212 → 140,282；StreamingIP 1,983 → 21，TelegramIP 按官方集合折叠为 11 条，GamesIP 41 → 8，JapanIP 移除五个全运营商 ASN。AI/Meta/X 再准入使用新 RDAP 证据。
- ChinaIP 锁定重建为 11,067 条，保留排除和受控范围；ChinaDomain 未通过新增候选可信度门槛，原 106,962 条保持。修复过期探测的超时误判与同日重复计数；21,906 个域名值复核未产生确认死亡结论。
- 匹配、分析和双端生成使用真实 MMDB、明确 DNS 状态与逻辑集合减法；CIDR 折叠保留尾参。模型下载/服务族归属补齐，缺乏证据的共享资源和 ProxyGFW 扩张未采用。
- 当批 4,750 条场景断言、84 条对抗断言通过；静态无 P0/P1/P2，3 个既有 P3。`8c92cbb` 发布状态 **PUBLISHED_AND_VERIFIED**。
- 最终按用户要求恢复正式 `@main` 地址：CDN 105/105 文件一致，Surge 52/52 资源就绪、90/90 原生见证通过；隔离 Mihomo 加载 52 表，双栈 DNS 与 8/8 连接策略验证通过。未据此宣称生产 Clash 已加载、账户同步成功或日常 FINAL 下降。[当批完整证据](https://github.com/yhyfhgs/surge-rules/blob/caf887f791185f46c371d482788af690677c4573/docs/evidence/2026-09-13-domain-ip-v2.md)。

## 历史索引

- [本次精简前的日志](https://github.com/yhyfhgs/surge-rules/blob/caf887f791185f46c371d482788af690677c4573/CHANGELOG.md)：2026-09-13 首轮仓库精简、OneDrive 恢复代理及失败直连试验、AI 上游维护、微软合并和旧 Clash 方案。
- [更早的完整日志](https://github.com/yhyfhgs/surge-rules/blob/9ebce49d8644dbe982fdcddfc62eb46296a7b277/CHANGELOG.md)：2026-09-02 及之前的治理、验证和发布批次。
- [历史审计报告](https://github.com/yhyfhgs/surge-rules/blob/9ebce49d8644dbe982fdcddfc62eb46296a7b277/docs/AUDIT_AND_GOVERNANCE_REPORT.md)：仅用于追溯，不作为现行设计或统计。
