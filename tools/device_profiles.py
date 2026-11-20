#!/usr/bin/env python3
"""Build private device profiles from one private inventory and public routing.

Never activates clients or writes the source profiles. Private input/output must
be outside this repository. See docs/DEVICE-PROFILES.md.
"""
import argparse
import copy
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from urllib.parse import urlsplit

import yaml

from prepare_profiles import (
    ROOT, section, replace_section, set_general, surge_candidate,
    clash_candidate,
)
from render_surge_rules import BASE_URL
from routing_manifest import load_routing_manifest

TAILNET = ['100.64.0.0/10', 'fd7a:115c:a1e0::/48']
CONTROL_DOMAINS = ['tailscale.com', 'tailscale.io', 'tailscale.net']
VARIANTS = {
    'mac': ('Surge-Mac.conf', False),
    'ios': ('Surge-iOS.conf', False),
    'windows': ('Clash-Windows.yaml', False),
    'windows-campus': ('Clash-Windows-Campus.yaml', True),
    'gateway': ('Surge-Macmini-Campus.conf', True),
}


def encrypted_dns_pools():
    pools = json.loads((ROOT / 'config/device-dns.json').read_text())
    if set(pools) != {'global', 'direct'}:
        raise ValueError('device DNS requires global and direct pools')
    for servers in pools.values():
        if not isinstance(servers, list) or not servers or len(set(servers)) != len(servers):
            raise ValueError('device DNS pools must contain unique encrypted endpoints')
        for endpoint in servers:
            url = urlsplit(endpoint)
            if (url.scheme not in ('https', 'tls') or url.username or url.password
                    or url.query or url.fragment or any(c in endpoint for c in ',\r\n')):
                raise ValueError('device DNS requires verified DoH/DoT without option overrides')
            ipaddress.ip_address(url.hostname)
    return pools


def private_path(value):
    path = Path(value).expanduser().resolve()
    if path == ROOT or ROOT in path.parents:
        raise ValueError('private paths must be outside the public repository')
    return path


def save_private(path, content):
    path = private_path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temp = tempfile.mkstemp(dir=path.parent, prefix='.profile-')
    try:
        with os.fdopen(fd, 'w') as f:
            f.write(content)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def assignments(body):
    result = {}
    for line in body.splitlines():
        if not line.strip() or line.lstrip().startswith(('#', ';', '//')):
            continue
        if '=' not in line:
            raise ValueError('invalid profile assignment')
        name, value = map(str.strip, line.split('=', 1))
        if name in result:
            raise ValueError('duplicate profile assignment')
        result[name] = value
    return result


def remove_section(text, name):
    return re.sub(r'(?ms)^\[' + re.escape(name) + r'\]\s*\n.*?(?=^\[|\Z)', '', text)


def drop_general(text, keys):
    body = section(text, 'General')[2]
    for key in keys:
        body = re.sub(r'(?m)^[ \t]*' + re.escape(key) + r'\s*=.*\n?', '', body)
    return replace_section(text, 'General', body)


def merge_general_list(text, key, values, remove=(), remove_ips=()):
    current = assignments(section(text, 'General')[2]).get(key, '')
    items = [v.strip() for v in current.split(',') if v.strip() and v.strip() not in remove]
    if remove_ips:
        retained = []
        for item in items:
            try:
                network = ipaddress.ip_network(item)
            except ValueError:
                retained.append(item)
                continue
            # Match exact IPs/host CIDRs, including alternate IPv6 spellings.
            if network.num_addresses != 1 or network.network_address not in remove_ips:
                retained.append(item)
        items = retained
    return set_general(text, {key: ', '.join(dict.fromkeys(items + values))})


def initialize(mac, ios, clash, gateway=None):
    """Capture protocol parameters once; server address is stored only once."""
    m, i = Path(mac).read_text(), Path(ios).read_text()
    gateway_text = Path(gateway).read_text() if gateway else None
    c = yaml.safe_load(Path(clash).read_text())
    mn = assignments(section(m, 'Proxy')[2])
    cn = {n['name']: n for n in c['proxies']}
    if len(cn) != len(c['proxies']) or set(mn) != set(cn):
        raise ValueError('Surge/Clash node inventories must have identical unique names')
    nodes = []
    for name, value in mn.items():
        parts = [p.strip() for p in value.split(',')]
        if len(parts) < 3 or parts[0] == 'tailscale':
            raise ValueError('desktop node inventory needs ordinary remote proxies')
        ipaddress.ip_address(parts[1])
        other = copy.deepcopy(cn[name])
        if parts[1] != str(other.pop('server')):
            raise ValueError('cross-protocol server disagreement; resolve before initialization')
        other.pop('name')
        nodes.append({'name': name, 'server': parts[1],
                      'surge': [parts[0], *parts[2:]], 'clash': other})
    groups = []
    cg = {g['name']: g for g in c['proxy-groups']}
    for name, value in assignments(section(m, 'Proxy Group')[2]).items():
        parts = [p.strip() for p in value.split(',')]
        members = [p for p in parts[1:] if '=' not in p]
        other = copy.deepcopy(cg[name])
        if members != other.pop('proxies'):
            raise ValueError('cross-protocol group membership disagreement')
        other.pop('name')
        groups.append({'name': name, 'members': members,
                       'surge': [parts[0], *[p for p in parts[1:] if '=' in p]], 'clash': other})
    # A newer desktop profile can retain an old address in its bypass settings
    # while the older mobile profile still identifies it as a node endpoint.
    # Collect addresses across every reference before normalizing any base.
    historical_servers = {str(n['server']) for n in c['proxies']}
    for text in (m, i, gateway_text):
        if text is None:
            continue
        for value in assignments(section(text, 'Proxy')[2]).values():
            parts = [p.strip() for p in value.split(',')]
            if len(parts) > 2 and parts[0] != 'tailscale':
                historical_servers.add(parts[1])
    def base(text):
        # Rendering adds only the current inventory endpoints back to each base.
        servers = sorted(historical_servers)
        for key in ('skip-proxy', 'tun-excluded-routes'):
            text = merge_general_list(text, key, [],
                                      remove=servers + [s + '/32' for s in servers if ':' not in s] +
                                      [s + '/128' for s in servers if ':' in s])
        text = replace_section(text, 'Rule', '# Generated at build time\nFINAL,Final,dns-failed')
        return replace_section(replace_section(text, 'Proxy', ''), 'Proxy Group', '')
    ios_nodes = assignments(section(i, 'Proxy')[2])
    ts = {n: v for n, v in ios_nodes.items() if v.split(',')[0].strip() == 'tailscale'}
    if len(ts) != 1:
        raise ValueError('expected one native iOS Tailscale policy')
    c.pop('proxies'); c.pop('proxy-groups')
    return {'version': 1, 'nodes': nodes, 'groups': groups,
            'bases': {'mac': base(m), 'ios': base(i), 'clash': c,
                      'gateway': base(gateway_text) if gateway_text else None},
            'ios_tailscale': ts,
            'campus': {'confirmed_on_campus': False, 'dns': [],
                       'extra_domains': [], 'extra_cidrs': []},
            'tailscale': {'extra_routes': [], 'magic_domains': [],
                          'mac_transport_processes': [], 'windows_transport_processes': [],
                          'process_exception_reason': ''}}


def validate_inventory(data):
    if data.get('version') != 1:
        raise ValueError('unsupported inventory version')
    names = [n['name'] for n in data['nodes']]
    groups = [g['name'] for g in data['groups']]
    if len(set(names + groups)) != len(names + groups):
        raise ValueError('duplicate node/group names')
    known = set(names + groups + ['DIRECT', 'REJECT'])
    if len(data['ios_tailscale']) != 1:
        raise ValueError('expected one native iOS Tailscale policy')
    if set(data['ios_tailscale']) & known:
        raise ValueError('native iOS Tailscale policy name collides with a node, group or built-in policy')
    for node in data['nodes']:
        ipaddress.ip_address(node['server'])
        if 'server' in node['clash'] or 'name' in node['clash']:
            raise ValueError('node server/name must have a single source')
        for param in node['surge'][2:]:
            if param.startswith('underlying-proxy=') and param.split('=', 1)[1] not in known:
                raise ValueError('unknown Surge dialer')
        if node['clash'].get('dialer-proxy', 'DIRECT') not in known:
            raise ValueError('unknown Clash dialer')
    graph = {}
    for group in data['groups']:
        if not group['members'] or set(group['members']) - known:
            raise ValueError('empty group or unknown member')
        graph[group['name']] = group['members']
    for node in data['nodes']:
        graph[node['name']] = [node['clash'].get('dialer-proxy', 'DIRECT')]
        graph[node['name']] += [p.split('=', 1)[1] for p in node['surge'][2:]
                               if p.startswith('underlying-proxy=')]
    def visit(n, stack):
        if n in stack:
            raise ValueError('proxy dependency cycle')
        for member in graph.get(n, []):
            visit(member, stack | {n})
    for name in graph:
        visit(name, set())
    ts = data['tailscale']
    for key in ('extra_routes',):
        for route in ts[key]:
            ipaddress.ip_network(route, strict=True)
    for route in data['campus']['extra_cidrs']:
        ipaddress.ip_network(route, strict=True)
    if (ts['mac_transport_processes'] or ts['windows_transport_processes']) and not ts['process_exception_reason'].strip():
        raise ValueError('transport process exceptions require a recorded reason')
    for field in ('mac_transport_processes', 'windows_transport_processes', 'magic_domains'):
        for value in ts[field]:
            if not value or any(c in value for c in ',\r\n'):
                raise ValueError('invalid transport selector')
    allowed = {'mac_transport_processes': {'tailscaled', 'io.tailscale.ipn.macsys.network-extension',
                                         'io.tailscale.ipn.macos.network-extension'},
               'windows_transport_processes': {'tailscaled.exe'}}
    for key, values in allowed.items():
        if set(ts[key]) - values:
            raise ValueError('only explicit Tailscale transport process exemptions are supported')
    for domain in data['campus']['extra_domains'] + ts['magic_domains']:
        if not re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?', domain) or '.' not in domain:
            raise ValueError('invalid private domain suffix')
    for resolver in data['campus']['dns']:
        if resolver != 'system':
            address = ipaddress.ip_address(resolver)
            if address.is_loopback or address in ipaddress.ip_network('198.18.0.0/15'):
                raise ValueError('campus DNS must not point back to the proxy listener')


def rules_from_list(name):
    return [line.strip().split(' #', 1)[0] for line in (ROOT / 'lists' / (name + '.list')).read_text().splitlines()
            if line.strip() and not line.lstrip().startswith('#')]


def campus_domains(data):
    config = json.loads((ROOT / 'config/campus-services.json').read_text())
    entries = rules_from_list('PKU') + rules_from_list('Academic')
    entries += ['DOMAIN-SUFFIX,' + d for family in config['families'] for d in family['suffixes']]
    entries += ['DOMAIN-SUFFIX,' + d for d in data['campus']['extra_domains']]
    # All entries in this overlay have one policy. Remove redundant children.
    domains = {r.split(',', 1)[1] for r in entries}
    return ['DOMAIN-SUFFIX,' + d for d in sorted(domains)
            if not any('.'.join(d.split('.')[i:]) in domains for i in range(1, len(d.split('.'))))]


def magic_domains(data):
    # Quad100 owns the whole ts.net namespace. Inventory entries can extend
    # this set, never narrow it to a particular tailnet or enumerate peers.
    domains = {'ts.net', *data['tailscale']['magic_domains']}
    return sorted(d for d in domains
                  if not any(d.endswith('.' + parent) for parent in domains if parent != d))


def host_patterns(domains):
    return [host for domain in domains for host in (domain, '*.' + domain)]


def campus_bypass(data):
    domains = [r.split(',', 1)[1] for r in rules_from_list('PKU')] + data['campus']['extra_domains']
    routes = [r.split(',')[1] for r in rules_from_list('PKUIP')] + data['campus']['extra_cidrs']
    # A physical-campus exclusion must never override a separately routed VPN
    # subnet or the proxy's DNS/fake-IP listener ranges.
    protected = TAILNET + data['tailscale']['extra_routes'] + ['198.18.0.0/15', 'fd00:6152::/32']
    for route in routes:
        network = ipaddress.ip_network(route)
        if any(network.overlaps(ipaddress.ip_network(p)) for p in protected):
            raise ValueError('campus bypass overlaps VPN or proxy listener routes')
    return host_patterns(domains), list(dict.fromkeys(routes))


def prelude(data, variant):
    mobile = variant == 'ios'
    ts = data['tailscale']
    domains = magic_domains(data)
    policy = next(iter(data['ios_tailscale'])) if mobile else 'DIRECT'
    rules = ['DOMAIN-SUFFIX,' + d + ',' + policy for d in domains]
    routes = TAILNET + ts['extra_routes']
    rules += [('IP-CIDR6' if ':' in r else 'IP-CIDR') + ',' + r + ',' + policy + ',no-resolve' for r in routes]
    if not mobile:
        rules += ['DOMAIN-SUFFIX,' + d + ',DIRECT' for d in CONTROL_DOMAINS]
        key = 'windows_transport_processes' if variant.startswith('windows') else 'mac_transport_processes'
        rules += ['PROCESS-NAME,' + p + ',DIRECT' for p in ts[key]]
    return rules


def surge_profile(data, variant, routing):
    base = data['bases'][variant]
    if not base:
        raise ValueError('gateway source profile is required')
    ts = data['tailscale']
    routes = TAILNET + ts['extra_routes']
    networks = [ipaddress.ip_network(r) for r in routes]
    servers = {n['server']: ipaddress.ip_address(n['server']) for n in data['nodes']}
    tailnet_servers = {ip for ip in servers.values() if any(ip in network for network in networks)}
    nodes = []
    for node in data['nodes']:
        params = list(node['surge'])
        if variant == 'ios' and servers[node['server']] in tailnet_servers:
            if any(p.split('=', 1)[0].strip() == 'underlying-proxy' for p in params[2:]):
                raise ValueError('Tailscale endpoint has conflicting existing Surge underlying-proxy')
            params.append('underlying-proxy=' + next(iter(data['ios_tailscale'])))
        nodes.append(node['name'] + ' = ' + ', '.join([params[0], node['server'], *params[1:]]))
    if variant == 'ios':
        nodes += [n + ' = ' + v for n, v in data['ios_tailscale'].items()]
    else:
        for name in re.findall(r'^\[(Tailscale [^\n]+)\]', base, re.M):
            base = remove_section(base, name)
    groups = [g['name'] + ' = ' + ', '.join([g['surge'][0], *g['members'], *g['surge'][1:]]) for g in data['groups']]
    base = replace_section(replace_section(base, 'Proxy', '\n'.join(nodes)), 'Proxy Group', '\n'.join(groups))
    dns = encrypted_dns_pools()
    result, _ = surge_candidate(base, routing, BASE_URL,
                                global_dns=dns['global'], direct_dns=dns['direct'])
    # Restore the imported design: captured port-53 queries enter Surge's
    # resolver, whose ordered Host mappings select their upstream. OS routes
    # owned by another VPN remain a separate boundary, checked on each device.
    result = set_general(result, {'hijack-dns': '*:53'})
    skip_remove_ips = tailnet_servers if variant == 'ios' else set()
    tun_remove_ips = tailnet_servers if variant == 'ios' else {ip for ip in tailnet_servers if ip.version == 4}
    result = merge_general_list(result, 'skip-proxy',
                                [s for s, ip in servers.items() if ip not in skip_remove_ips],
                                remove_ips=skip_remove_ips)
    result = merge_general_list(result, 'tun-excluded-routes',
                                [s + '/' + str(ip.max_prefixlen) for s, ip in servers.items() if ip not in tun_remove_ips],
                                remove_ips=tun_remove_ips)
    if variant == 'ios':
        # Tailnet must enter the native policy, never escape through OS bypass.
        for key in ('skip-proxy', 'tun-excluded-routes'):
            result = merge_general_list(result, key, [],
                                        remove=routes + ['fc00::/7'] + host_patterns(['ts.net'] + magic_domains(data)))
        result = merge_general_list(result, 'always-real-ip', [], remove=host_patterns(['ts.net'] + magic_domains(data)))
        if not assignments(section(result, 'General')[2]).get('always-real-ip'):
            result = drop_general(result, ['always-real-ip'])
    else:
        # IPv4 exclusions can install a physical-gateway route that wins over
        # Tailscale's same-prefix route. Preserve IPv6 exclusions: removing the
        # existing ULA exclusion made peer IPv6 fall into Surge's default route
        # in the macOS live check. Do not assume identical address-family behavior.
        result = merge_general_list(result, 'tun-excluded-routes',
                                    [r for r in routes if ':' in r],
                                    remove=[r for r in routes if ':' not in r])
        patterns = host_patterns(magic_domains(data))
        result = merge_general_list(result, 'skip-proxy', routes + patterns,
                                    remove=host_patterns(['ts.net']))
        result = merge_general_list(result, 'always-real-ip', patterns,
                                    remove=host_patterns(['ts.net']))
        host = section(result, 'Host')[2]
        for h in host_patterns(['ts.net'] + magic_domains(data)):
            host = re.sub(r'(?m)^' + re.escape(h) + r'\s*=.*\n?', '', host)
        # Match desktop control-plane DIRECT routing with direct encrypted DNS,
        # so reconnecting the independent VPN does not need the proxy DNS path.
        resolver = ','.join(dns['direct'])
        control_hosts = [h for d in CONTROL_DOMAINS for h in (d, '*.' + d)]
        for h in control_hosts:
            host = re.sub(r'(?m)^' + re.escape(h) + r'\s*=.*\n?', '', host)
        mappings = [h + ' = server:' + resolver for h in control_hosts]
        result = replace_section(result, 'Host', '\n'.join(mappings) + '\n' + host)
    # All Surge variants share namespace DNS, including native Tailscale on
    # iOS. Only desktops receive the OS-bypass/real-IP exceptions above.
    host = section(result, 'Host')[2]
    patterns = host_patterns(magic_domains(data))
    for h in patterns:
        host = re.sub(r'(?m)^' + re.escape(h) + r'\s*=.*\n?', '', host)
    private_hosts = [h + ' = server:100.100.100.100' for h in patterns]
    result = replace_section(result, 'Host', '\n'.join(private_hosts) + '\n' + host)
    extra = prelude(data, variant)
    campus_rules = []
    if variant == 'gateway':
        domains = campus_domains(data)
        campus_rules += [r + ',DIRECT' for r in domains]
        campus_rules += [r + ',DIRECT,no-resolve' for r in rules_from_list('PKUIP')]
        campus_rules += [('IP-CIDR6' if ':' in r else 'IP-CIDR') + ',' + r + ',DIRECT,no-resolve' for r in data['campus']['extra_cidrs']]
        dns = ','.join(data['campus']['dns'])
        host = section(result, 'Host')[2]
        mappings = [host + ' = server:' + dns for r in domains
                    for host in (r.split(',', 1)[1], '*.' + r.split(',', 1)[1])]
        result = replace_section(result, 'Host', '\n'.join(mappings) + '\n' + host)
        bypass_hosts, bypass_routes = campus_bypass(data)
        result = merge_general_list(result, 'always-real-ip', bypass_hosts)
        result = merge_general_list(result, 'skip-proxy', bypass_hosts + bypass_routes)
        result = merge_general_list(result, 'tun-excluded-routes', bypass_routes)
    rule_lines = section(result, 'Rule')[2].splitlines()
    if campus_rules:
        index = next(i for i, line in enumerate(rule_lines) if '/Reject.list,' in line) + 1
        rule_lines[index:index] = ['# Campus egress overlay'] + campus_rules
    result = replace_section(result, 'Rule', '# Device-specific routing\n' + '\n'.join(extra + rule_lines))
    return result


def clash_profile(data, variant, routing):
    base = copy.deepcopy(data['bases']['clash'])
    base['proxies'] = [dict(n['clash'], name=n['name'], server=n['server']) for n in data['nodes']]
    base['proxy-groups'] = [dict(g['clash'], name=g['name'], proxies=g['members']) for g in data['groups']]
    result, _ = clash_candidate(yaml.safe_dump(base, allow_unicode=True, sort_keys=False), routing)
    result = yaml.safe_load(result)
    dns = encrypted_dns_pools()
    result['dns']['default-nameserver'] = list(dns['direct'])
    result['dns']['proxy-server-nameserver'] = [s + '#DIRECT' for s in dns['direct']]
    result['dns']['direct-nameserver'] = [s + '#DIRECT' for s in dns['direct']]
    result['dns']['nameserver'] = [s + '#Proxy' for s in dns['global']]
    ts = data['tailscale']
    result['tun']['route-exclude-address'] = TAILNET + ts['extra_routes']
    # Windows strict-route's DNS firewall conflicts with Tailscale NRPT/Quad100.
    result['tun']['strict-route'] = False
    for domain in magic_domains(data):
        result['dns']['nameserver-policy']['+.' + domain] = ['100.100.100.100']
    for domain in CONTROL_DOMAINS:
        result['dns']['nameserver-policy']['+.' + domain] = list(result['dns']['direct-nameserver'])
    result['dns']['fake-ip-filter'] += ['+.' + d for d in magic_domains(data)]
    result['rules'] = prelude(data, variant) + result['rules']
    if variant == 'windows-campus':
        domains = campus_domains(data)
        ips = rules_from_list('PKUIP')
        index = result['rules'].index('RULE-SET,Reject,REJECT') + 1
        result['rules'][index:index] = ([r + ',DIRECT' for r in domains] +
                                       [r + ',DIRECT,no-resolve' for r in ips] +
                                       [('IP-CIDR6' if ':' in r else 'IP-CIDR') + ',' + r + ',DIRECT,no-resolve' for r in data['campus']['extra_cidrs']])
        _, bypass_routes = campus_bypass(data)
        result['tun']['route-exclude-address'] += bypass_routes
        for rule in domains:
            domain = rule.split(',', 1)[1]
            result['dns']['nameserver-policy']['+.' + domain] = [
                s if s == 'system' else s + '#DIRECT' for s in data['campus']['dns']]
        result['dns']['fake-ip-filter'] += ['+.' + d for d in
                [r.split(',', 1)[1] for r in rules_from_list('PKU')] + data['campus']['extra_domains']]
    return yaml.safe_dump(result, allow_unicode=True, sort_keys=False)


def build(data, selected=None):
    validate_inventory(data)
    routing = load_routing_manifest(str(ROOT / 'config/routing.json'), str(ROOT / 'lists'))
    artifacts = {}
    for variant in selected or VARIANTS:
        name, campus = VARIANTS[variant]
        if campus and (not data['campus']['confirmed_on_campus'] or not data['campus']['dns']):
            raise ValueError('campus profiles require confirmed campus egress and explicit campus DNS')
        artifacts[name] = (clash_profile(data, variant, routing) if variant.startswith('windows')
                           else surge_profile(data, variant, routing))
    artifacts['verge-settings.merge.yaml'] = 'enable_system_proxy: false\nenable_tun_mode: true\n'
    for script in ('tailscale-dns-off.sh', 'tailscale-dns-off.ps1'):
        artifacts[script] = (ROOT / 'config/device-scripts' / script).read_text()
    artifacts['README.md'] = '''# 五类配置的手动分发

这些文件包含节点凭据及可能存在的私有证书，请仅向自己的设备分发。

| 配置 | 设备与用途 |
|---|---|
| Surge-Mac.conf | 本机 Mac；与独立 Tailscale 客户端共存 |
| Surge-iOS.conf | 手机；使用 Surge 原生 Tailscale 节点 |
| Clash-Windows.yaml | 普通 Windows；TUN 开启、独立 Tailscale 放行 |
| Clash-Windows-Campus.yaml | 校园内 Windows；增加期刊、校园及软件授权直连 |
| Surge-Macmini-Campus.conf | 校园内 Mac mini 网关；Tailscale 放行及校园直连 |

## 导入

- Surge：导入对应完整配置，再按需切换。手机原生 Tailscale 在新设备上需自行登录；保留原 section 名称，避免丢失已有身份关联。
- Clash Verge Rev：导入对应完整 YAML；关闭系统代理、开启 TUN、关闭严格路由和 DNS 覆写。核对运行配置中的 route-exclude-address，防止应用里保存的 TUN 设置覆盖导入值。
- verge-settings.merge.yaml 是应用偏好片段，不是订阅文件。仅合并其中两个字段，不能用它覆盖整个 verge.yaml。导入普通配置不能自动改变应用偏好。
- Mac mini：在 Surge 应用中启用已有的 VM Gateway 设置，客户端使用应用显示的网关/DNS。网关主机自身继续使用校园物理出口及 DHCP DNS，不能把自己指向自己的 VM Gateway。需要按规则处理的网关客户端关闭 UDP Fast Path。

## 校园访问

校园版仅用于校园网内，DIRECT 保留实际校园出口。期刊和软件账号仍需具备学校授权。
校园解析器由上一级 inventory.json 的 campus.dns 明确维护；本批使用北大官方文档列出的 162.105.129.122、162.105.129.88，避免依赖会被其他 VPN 改写的系统 DNS。需在实际校园设备验证可达性；院系 DNS 不同时改为管理员核实的地址。
学校许可证服务器域名/IP 可在 campus.extra_domains / extra_cidrs 补充，不要把整个 Microsoft 或 IBM 流量都改为直连。
校园内网域名返回真实 IP；校园地址段在 Mac mini 同时写入 tun-excluded-routes 与 skip-proxy，在 Windows 写入 route-exclude-address。域名解析到这些网段后，业务连接才可以完全绕过；公网期刊/CDN 继续 DIRECT。新增校园排除不得与 Tailscale 子网或 Fake IP 池重叠。

## Tailscale

桌面设备统一关闭 Tailscale 的“使用 Tailscale DNS”，由 Surge/Mihomo 接管普通 DNS。
先启用对应代理配置，再在 Mac/Mac mini 执行 `sh ./tailscale-dns-off.sh`，在 Windows PowerShell 执行 `./tailscale-dns-off.ps1`；也可以在 Tailscale 设置里手动取消该选项。
脚本只执行 `tailscale set --accept-dns=false`，生成过程不会运行它，不改变节点身份、子网公告或 Exit Node 设置。导入 Surge/Mihomo 配置本身不能修改这个 Tailscale 客户端开关。
保留 tailnet 管理后台的 MagicDNS：仅内网设备名由代理软件定向查询 100.100.100.100，普通公网查询使用代理配置中的 DNS，校园域名走校园 DNS。关闭 accept-dns 后 Quad100 仍可回答 MagicDNS；这不会让 Tailscale 接管系统 DNS。
ts.net 整个域统一交给 Quad100：Surge 使用 ts.net / *.ts.net，Mihomo 使用 +.ts.net，自动覆盖所有层级子域，不逐台设备或逐个 tailnet 枚举。tailscale.magic_domains 仅用于添加其他专用解析域，不会缩小 ts.net 的覆盖范围；手机仍通过 Surge 原生 Tailscale 策略连接。
关闭 DNS 接管后不依赖 Tailscale 自动配置的搜索后缀，请使用完整的节点名（设备名.实际tailnet.ts.net）；如需短名称应另行配置明确别名。
Mac/Mac mini 不将 Tailscale IPv4 网段或额外 IPv4 子网写入 Surge 的 tun-excluded-routes，避免排除项生成的物理网关路由抢走流量；保留现有 IPv6 排除设置，逐机验证两种地址均进入 Tailscale 隧道。Windows 保留 Mihomo 的 route-exclude-address。
MagicDNS 使用 Quad100，Tailscale 传输进程直连；Windows strict-route 关闭是兼容性选择，不代表所有应用 DNS 均被接管。
Surge 显式设置 hijack-dns = *:53；已进入 VIF 的普通 DNS 交给内部解析器，再由有序 Host / RULE-SET 映射选择上游。2026-10-05 本机 UDP 53 查询返回 Fake IP，但 TCP 53 查询返回公网真实 IP；该设置不能作为 TCP、IPv6 或应用自带 DoH/DoT 全部接管的证明。Mihomo 同时配置 UDP 与 TCP 53 劫持，仍需在目标 Windows 实测。
完全绕过与 DIRECT 不同：Surge 的 tun-excluded-routes 只接受 IP 网段，skip-proxy 处理系统代理旁路，域名还需要 always-real-ip 返回真实地址且该地址确实走排除路由。不能把域名通配符直接放入 tun-excluded-routes，也不能把 Fake IP 地址池整体排除。直接发往已经绕过的 DNS 地址（例如 Quad100）的请求不受 VIF 劫持；正常系统查询先进入代理解析器。
公网 DNS 使用 DoH + DoT：海外 Google/Cloudflare、国内阿里/DNSPod 各四个端点，由 rules/config/device-dns.json 统一维护。桌面 Tailscale 控制域名也显式使用国内直连加密 DNS，避免依赖代理 DNS 路径。Surge 校验证书并按规则选择加密 DNS 出站；普通 dns-server 仅用于连通性检查及加密 DNS 域名引导，并非普通公网查询的并行上游。Surge 对池内端点并发查询、采用先返回的结果，不是按配置顺序逐个故障切换。
MagicDNS、局域网和校园解析保留专用路径；校园 system 上游是否加密取决于校园服务，不能宣称所有 DNS 均经 DoH。
手机使用 Surge 内置 Tailscale，仅复制配置不会复制登录身份。额外已批准子网在 inventory.json 的 tailscale.extra_routes 统一维护。
Mac mini 的独立 Tailscale 必须保持自己的路由与权限配置。配置文件不会创建子网路由器或 Exit Node；tailscaled 重新发起的入站转发也会直连校园出口。

## 以后统一更新

不要分别修改这五份产物。节点地址改上一级 inventory.json 的 nodes[].server；协议凭据在同一节点的 surge/clash 字段分别维护；组成员只改 groups[].members。
在公开 rules 仓库执行：

```sh
python3 tools/surge2clash.py
python3 tests/device_profiles_test.py
python3 tools/device_profiles.py build --inventory ../DeviceProfiles/inventory.json --out ../DeviceProfiles/dist
python3 tools/device_profiles.py build --check --inventory ../DeviceProfiles/inventory.json --out ../DeviceProfiles/dist
```

生成会先完成三份 Surge 和两份 Mihomo 的原生语法检查，再写入文件；SHA256SUMS 用于核对同一批产物。
公共规则仍引用 @main；改动公共列表后须完成仓库的发布验证才能分发。不会自动替换当前活动配置、重载客户端或改变系统代理。

## 上机验收

检查 Tailscale 节点 IP 和 MagicDNS、校园门户、真实许可证服务器、期刊机构识别、IPv4/IPv6 和重启后的路由。
本机静态/原生语法验证不代表已完成手机、Windows 或 Mac mini 的真实网络及授权登录测试。
'''
    paths = [ROOT / 'config/routing.json', ROOT / 'config/campus-services.json', ROOT / 'config/mihomo-runtime.yaml',
             ROOT / 'config/device-dns.json',
             Path(__file__), ROOT / 'tools/prepare_profiles.py', ROOT / 'tools/render_surge_rules.py',
             ROOT / 'tools/rule_syntax.py', *sorted((ROOT / 'config/device-scripts').iterdir()),
             *sorted((ROOT / 'lists').glob('*.list'))]
    artifacts['BUILD.json'] = json.dumps({
        'inventory_sha256': hashlib.sha256(json.dumps(data, ensure_ascii=False, sort_keys=True).encode()).hexdigest(),
        'source_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        'profiles': list(selected or VARIANTS),
        'desktop_dns': {'owner': 'Surge/Mihomo', 'tailscale_accept_dns': False,
                        'magicdns_upstream_only': '100.100.100.100',
                        'requires_manual_client_setting': True},
    }, ensure_ascii=False, indent=2) + '\n'
    artifacts['SHA256SUMS'] = ''.join(hashlib.sha256(v.encode()).hexdigest() + '  ' + k + '\n' for k, v in artifacts.items())
    return artifacts


def validate_native(artifacts):
    """Use local rules/MMDB, with no runtime instance, TUN, or network download."""
    surge = shutil.which('surge-cli') or '/Applications/Surge.app/Contents/Applications/surge-cli'
    mihomo = shutil.which('mihomo')
    if not Path(surge).is_file() or not mihomo:
        raise ValueError('native validation requires surge-cli and mihomo')
    country = Path.home() / 'Library/Application Support/com.nssurge.surge-mac/GeoLite2-Country.mmdb'
    asn = Path('/Applications/Surge.app/Contents/Resources/GeoLite2-ASN.mmdb')
    if not country.is_file() or not asn.is_file():
        raise ValueError('native validation requires the actual Country/ASN MMDB files')
    with tempfile.TemporaryDirectory(prefix='device-profile-check-') as temp:
        folder = Path(temp)
        shutil.copyfile(country, folder / 'Country.mmdb')
        shutil.copyfile(asn, folder / 'ASN.mmdb')
        shutil.copytree(ROOT / 'clash', folder / 'providers')
        for name, text in artifacts.items():
            path = folder / name
            if name.endswith('.conf'):
                save_private(path, text.replace(BASE_URL, str(ROOT / 'lists')))
                command = [surge, '--check', str(path)]
            elif name.startswith('Clash-'):
                data = yaml.safe_load(text)
                data['rule-providers'] = {n: {'type': 'file', 'behavior': 'classical', 'format': 'text',
                                             'path': './providers/' + n + '.list'} for n in data['rule-providers']}
                save_private(path, yaml.safe_dump(data, allow_unicode=True, sort_keys=False))
                command = [mihomo, '-t', '-d', str(folder), '-f', str(path)]
            else:
                continue
            proc = subprocess.run(command, capture_output=True, text=True, timeout=90)
            if proc.returncode:
                # Native errors can contain credential-bearing source lines.
                log = Path(tempfile.mkdtemp(prefix='device-profile-error-')) / 'native.log'
                save_private(log, proc.stdout + proc.stderr)
                raise ValueError('native check failed for ' + name + '; private log: ' + str(log))
            print('Native syntax OK: ' + name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    init = sub.add_parser('init')
    for name in ('mac', 'ios', 'clash', 'inventory'):
        init.add_argument('--' + name, required=True)
    init.add_argument('--gateway')
    generate = sub.add_parser('build')
    generate.add_argument('--inventory', required=True)
    generate.add_argument('--out', required=True)
    generate.add_argument('--variants', nargs='+', choices=list(VARIANTS))
    generate.add_argument('--check', action='store_true', help='validate and compare existing outputs without writing')
    args = parser.parse_args()
    if args.command == 'init':
        dest = private_path(args.inventory)
        if dest.exists():
            raise ValueError('inventory already exists; edit its canonical values instead')
        data = initialize(private_path(args.mac), private_path(args.ios), private_path(args.clash),
                          private_path(args.gateway) if args.gateway else None)
        save_private(dest, json.dumps(data, ensure_ascii=False, indent=2) + '\n')
        print('Private inventory created; no client state changed.')
    else:
        source = private_path(args.inventory)
        out = private_path(args.out)
        from surge2clash import build_all, read_existing
        expected, _, _, _ = build_all()
        if any(read_existing(n) != t.encode() for n, t in expected.items()):
            raise ValueError('Clash mirror is stale; run tools/surge2clash.py first')
        artifacts = build(json.loads(source.read_text()), args.variants)
        validate_native(artifacts)
        if args.check:
            drift = [name for name, content in artifacts.items()
                     if not (out / name).is_file() or (out / name).read_text() != content]
            if drift:
                raise ValueError('generated output drift: ' + ', '.join(drift))
            print('All private outputs match current sources.')
            return
        # Complete rendering and native validation before any output is replaced.
        for name, content in artifacts.items():
            save_private(out / name, content)
        print('Generated %d private artifacts; no client state changed.' % len(artifacts))


if __name__ == '__main__':
    main()
