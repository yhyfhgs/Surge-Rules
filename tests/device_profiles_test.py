#!/usr/bin/env python3
"""五类私有配置的同步、DNS、边界与凭据保留回归；只使用中性节点。"""
import copy
import fnmatch
import ipaddress
import json
from pathlib import Path
import sys
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
from device_profiles import build, campus_domains, campus_bypass, private_path, validate_inventory, assignments, initialize, TAILNET, CONTROL_DOMAINS
from prepare_profiles import section, set_general
from routing_manifest import load_routing_manifest
from render_surge_rules import render_rules
from engine import Engine


def fixture():
    routing = load_routing_manifest(str(ROOT / 'config/routing.json'), str(ROOT / 'lists'))
    policies = sorted({r['policy'] for r in routing if r['policy'] not in ('DIRECT', 'REJECT')} | {'Final', 'Proxy'})
    base = '''[General]
dns-server = 223.5.5.5
skip-proxy = localhost, 100.64.0.0/10, fc00::/7
always-real-ip = *.ts.net, device.lan
hijack-dns = *:53
[Proxy]
[Proxy Group]
[Rule]
FINAL,Final,dns-failed
[MITM]
hostname = *.example.org
'''
    return {'version': 1,
            'nodes': [{'name': 'Remote', 'server': '192.0.2.1',
                       'surge': ['snell', '443', 'psk=neutral-secret', 'version=5'],
                       'clash': {'type': 'socks5', 'port': 443, 'username': 'neutral', 'password': 'secret'}}],
            'groups': [{'name': n, 'members': ['Remote'], 'surge': ['select'], 'clash': {'type': 'select'}} for n in policies],
            'bases': {'mac': base, 'ios': base + '\n[Tailscale test]\ninteractive-login = true\n', 'gateway': base, 'clash': {}},
            'ios_tailscale': {'Mesh': 'tailscale, section-name=test'},
            'campus': {'confirmed_on_campus': True, 'dns': ['system'], 'extra_domains': [], 'extra_cidrs': []},
            'tailscale': {'extra_routes': [], 'magic_domains': [], 'mac_transport_processes': [],
                          'windows_transport_processes': [], 'process_exception_reason': ''}}


def tailscale_proxy_fixture():
    data = fixture()
    data['ios_tailscale'] = {'Native Mesh': 'tailscale, section-name=test'}
    data['tailscale']['extra_routes'] = ['10.20.0.0/16', '2001:db8:20::/64']
    data['nodes'][0]['surge'].append('underlying-proxy=Ordinary IPv6')
    for name, server in (('Mesh IPv4', '100.64.0.7'), ('Mesh IPv6', 'fd7a:115c:a1e0::7'),
                         ('Subnet IPv4', '10.20.0.7'), ('Subnet IPv6', '2001:db8:20::7'),
                         ('Ordinary IPv6', '2001:db8:ffff::7')):
        data['nodes'].append({'name': name, 'server': server,
                              'surge': ['http', '8080', 'username=neutral', 'password=secret'],
                              'clash': {'type': 'http', 'port': 8080, 'username': 'neutral', 'password': 'secret'}})
    data['groups'][0]['members'] += [n['name'] for n in data['nodes'][1:]]
    data['groups'][0]['surge'].append('hidden=true')
    return data


class DeviceProfilesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = fixture()
        cls.artifacts = build(cls.data)

    def test_three_surges_share_nodes_and_credentials(self):
        for name in ('Surge-Mac.conf', 'Surge-iOS.conf', 'Surge-Macmini-Campus.conf'):
            text = self.artifacts[name]
            nodes = assignments(section(text, 'Proxy')[2])
            self.assertEqual(nodes['Remote'], 'snell, 192.0.2.1, 443, psk=neutral-secret, version=5')
            self.assertEqual(section(text, 'MITM')[2].strip(), 'hostname = *.example.org')
            self.assertIn('auto-quic-block = true', text)

    def test_one_server_edit_updates_all_five_and_bypass(self):
        data = copy.deepcopy(self.data)
        data['nodes'][0]['server'] = '192.0.2.2'
        artifacts = build(data)
        for name, text in artifacts.items():
            if name.endswith('.conf') or name.startswith('Clash-'):
                self.assertIn('192.0.2.2', text)
                self.assertNotIn('192.0.2.1', text)

    def test_import_removes_historical_mobile_endpoint_from_all_bases(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            old = '203.0.113.9'
            mac = set_general(self.artifacts['Surge-Mac.conf'], {
                'skip-proxy': 'localhost, ' + old,
                'tun-excluded-routes': old + '/32',
            })
            ios = self.artifacts['Surge-iOS.conf'].replace('192.0.2.1', old)
            paths = [folder / n for n in ('mac.conf', 'ios.conf', 'clash.yaml')]
            for path, text in zip(paths, (mac, ios, self.artifacts['Clash-Windows.yaml'])):
                path.write_text(text)
            data = initialize(*paths, gateway=paths[0])
            data['campus'] = copy.deepcopy(self.data['campus'])
            for base in ('mac', 'ios', 'gateway'):
                self.assertNotIn(old, data['bases'][base])
            for name, text in build(data).items():
                if name.endswith('.conf') or name.startswith('Clash-'):
                    self.assertNotIn(old, text)
                    self.assertIn('192.0.2.1', text)

    def test_mobile_native_tailnet_never_bypasses_to_os(self):
        text = self.artifacts['Surge-iOS.conf']
        general = assignments(section(text, 'General')[2])
        for key in ('tun-excluded-routes', 'skip-proxy'):
            self.assertNotIn('100.64.0.0/10', general[key])
            self.assertNotIn('fc00::/7', general[key])
        self.assertIn('IP-CIDR,100.64.0.0/10,Mesh,no-resolve', text)
        self.assertIn('IP-CIDR6,fd7a:115c:a1e0::/48,Mesh,no-resolve', text)
        self.assertEqual(general['always-real-ip'], 'device.lan')
        self.assertNotIn('PROCESS-NAME,', text)

    def test_mac_tailnet_routes_owned_by_tailscale_with_dns_capture(self):
        for name in ('Surge-Mac.conf', 'Surge-Macmini-Campus.conf'):
            text = self.artifacts[name]
            general = assignments(section(text, 'General')[2])
            self.assertNotIn('100.64.0.0/10', general['tun-excluded-routes'])
            self.assertIn('fd7a:115c:a1e0::/48', general['tun-excluded-routes'])
            self.assertEqual(general['hijack-dns'], '*:53')
            self.assertIn('*.ts.net = server:100.100.100.100', text)
            self.assertNotIn('[Tailscale ', text)

    def test_dns_capture_does_not_depend_on_imported_base(self):
        data = copy.deepcopy(self.data)
        for variant in ('mac', 'gateway', 'ios'):
            data['bases'][variant] = data['bases'][variant].replace('hijack-dns = *:53\n', '')
        for name, text in build(data).items():
            if name.endswith('.conf'):
                self.assertEqual(assignments(section(text, 'General')[2])['hijack-dns'], '*:53')

    def test_mac_removes_inherited_tailnet_exclusions_preserving_other_routes(self):
        data = copy.deepcopy(self.data)
        data['tailscale']['extra_routes'] = ['10.20.0.0/16']
        for variant in ('mac', 'gateway'):
            data['bases'][variant] = set_general(data['bases'][variant], {
                'tun-excluded-routes': ', '.join(TAILNET + ['10.20.0.0/16', '203.0.113.7/32']),
            })
        artifacts = build(data)
        for name in ('Surge-Mac.conf', 'Surge-Macmini-Campus.conf'):
            text = artifacts[name]
            excluded = assignments(section(text, 'General')[2])['tun-excluded-routes'].split(', ')
            campus = campus_bypass(data)[1] if name == 'Surge-Macmini-Campus.conf' else []
            self.assertEqual(set(excluded), {'203.0.113.7/32', '192.0.2.1/32', 'fd7a:115c:a1e0::/48', *campus})
            self.assertIn('IP-CIDR,10.20.0.0/16,DIRECT,no-resolve', text)

    def test_tailscale_proxy_endpoints_use_device_transport_without_inventory_changes(self):
        data = tailscale_proxy_fixture()
        original = copy.deepcopy(data)
        artifacts = build(data)
        for name in ('Surge-Mac.conf', 'Surge-Macmini-Campus.conf', 'Surge-iOS.conf'):
            mobile = name == 'Surge-iOS.conf'
            text = artifacts[name]
            nodes = assignments(section(text, 'Proxy')[2])
            general = assignments(section(text, 'General')[2])
            for node in data['nodes']:
                with self.subTest(profile=name, node=node['name']):
                    tailnet = node in data['nodes'][1:-1]
                    expected = ', '.join([node['surge'][0], node['server'], *node['surge'][1:]])
                    if mobile and tailnet:
                        expected += ', underlying-proxy=Native Mesh'
                    self.assertEqual(nodes[node['name']], expected)
                    address = ipaddress.ip_address(node['server'])
                    cidr = str(address) + '/' + str(address.max_prefixlen)
                    self.assertEqual(cidr in general['tun-excluded-routes'].split(', '),
                                     not tailnet or (not mobile and address.version == 6))
                    self.assertEqual(node['server'] in general['skip-proxy'].split(', '),
                                     not (mobile and tailnet))
            expected_groups = {g['name']: ', '.join([g['surge'][0], *g['members'], *g['surge'][1:]])
                               for g in data['groups']}
            self.assertEqual(assignments(section(text, 'Proxy Group')[2]), expected_groups)
        for name in ('Clash-Windows.yaml', 'Clash-Windows-Campus.yaml'):
            self.assertEqual(yaml.safe_load(artifacts[name])['proxies'],
                             [dict(n['clash'], name=n['name'], server=n['server']) for n in data['nodes']])
        self.assertEqual(data, original)

    def test_tailscale_proxy_inherited_exact_endpoint_exclusions(self):
        data = tailscale_proxy_fixture()
        selectors = {}
        for node in data['nodes'][1:-1]:
            address = ipaddress.ip_address(node['server'])
            spellings = {str(address), address.exploded.upper()}
            selectors[address] = spellings | {s + '/' + str(address.max_prefixlen) for s in spellings}
        inherited = [s for values in selectors.values() for s in sorted(values)]
        inherited += TAILNET + data['tailscale']['extra_routes'] + ['fc00::/7', '203.0.113.9/32']
        for variant in ('mac', 'gateway', 'ios'):
            data['bases'][variant] = set_general(data['bases'][variant], {
                'skip-proxy': ', '.join(['localhost', 'unrelated.example', *inherited]),
                'tun-excluded-routes': ', '.join(inherited),
            })
        artifacts = build(data, ['mac', 'gateway', 'ios'])
        for name in ('Surge-Mac.conf', 'Surge-Macmini-Campus.conf', 'Surge-iOS.conf'):
            general = assignments(section(artifacts[name], 'General')[2])
            for key in ('skip-proxy', 'tun-excluded-routes'):
                values = set(general[key].split(', '))
                self.assertIn('203.0.113.9/32', values)
                for address, inherited_selectors in selectors.items():
                    with self.subTest(profile=name, key=key, address=address):
                        remove = name == 'Surge-iOS.conf' or (key == 'tun-excluded-routes' and address.version == 4)
                        if remove:
                            self.assertFalse(values & inherited_selectors)
                        else:
                            self.assertTrue(inherited_selectors <= values)
            self.assertIn('unrelated.example', general['skip-proxy'].split(', '))

    def test_tailscale_proxy_conflicting_dialers_fail_without_mutation(self):
        for dialer in ('underlying-proxy=DIRECT', 'underlying-proxy=Remote', 'underlying-proxy = DIRECT'):
            with self.subTest(dialer=dialer):
                data = tailscale_proxy_fixture()
                data['nodes'][1]['surge'].append(dialer)
                original = copy.deepcopy(data)
                with self.assertRaisesRegex(ValueError, 'conflicting.*underlying-proxy'):
                    build(data, ['ios'])
                self.assertEqual(data, original)

    def test_native_tailscale_policy_must_be_unique_and_not_collide(self):
        data = fixture()
        for names, error in (([], 'one native iOS Tailscale policy'),
                             (['First', 'Second'], 'one native iOS Tailscale policy'),
                             (['Remote'], 'policy name collides'),
                             ([data['groups'][0]['name']], 'policy name collides'),
                             (['DIRECT'], 'policy name collides'),
                             (['REJECT'], 'policy name collides')):
            with self.subTest(names=names):
                data['ios_tailscale'] = {n: 'tailscale, section-name=test' for n in names}
                with self.assertRaisesRegex(ValueError, error):
                    validate_inventory(data)

    def test_windows_tun_and_dns_contract(self):
        for name in ('Clash-Windows.yaml', 'Clash-Windows-Campus.yaml'):
            data = yaml.safe_load(self.artifacts[name])
            self.assertTrue(data['tun']['enable'])
            self.assertFalse(data['tun']['strict-route'])
            self.assertTrue(set(TAILNET) <= set(data['tun']['route-exclude-address']))
            self.assertEqual(data['dns']['nameserver-policy']['+.ts.net'], ['100.100.100.100'])
            self.assertIn('+.ts.net', data['dns']['fake-ip-filter'])
            self.assertNotIn('enable_system_proxy', data)
        settings = yaml.safe_load(self.artifacts['verge-settings.merge.yaml'])
        self.assertEqual(settings, {'enable_system_proxy': False, 'enable_tun_mode': True})

    def test_tailscale_is_only_a_scoped_dns_upstream(self):
        for name in ('Clash-Windows.yaml', 'Clash-Windows-Campus.yaml'):
            dns = yaml.safe_load(self.artifacts[name])['dns']
            for field in ('nameserver', 'fallback', 'default-nameserver', 'direct-nameserver', 'proxy-server-nameserver'):
                self.assertNotIn('100.100.100.100', str(dns[field]))
        for name in ('Surge-Mac.conf', 'Surge-Macmini-Campus.conf'):
            general = assignments(section(self.artifacts[name], 'General')[2])
            self.assertNotIn('100.100.100.100', general['dns-server'])
            self.assertNotIn('100.100.100.100', general['encrypted-dns-server'])
        metadata = json.loads(self.artifacts['BUILD.json'])['desktop_dns']
        self.assertFalse(metadata['tailscale_accept_dns'])
        self.assertTrue(metadata['requires_manual_client_setting'])

    def test_custom_magic_namespace_selects_upstream_and_real_ip_together(self):
        data = copy.deepcopy(self.data)
        data['tailscale']['magic_domains'] = ['mesh.example.net']
        artifacts = build(data)
        for name in ('Surge-Mac.conf', 'Surge-Macmini-Campus.conf'):
            text = artifacts[name]
            hosts = assignments(section(text, 'Host')[2])
            general = assignments(section(text, 'General')[2])
            for selector in ('mesh.example.net', '*.mesh.example.net'):
                self.assertEqual(hosts[selector], 'server:100.100.100.100')
                for key in ('always-real-ip', 'skip-proxy'):
                    self.assertIn(selector, general[key].split(', '))
            self.assertEqual(hosts['*.ts.net'], 'server:100.100.100.100')
            self.assertIn('DOMAIN-SUFFIX,mesh.example.net,DIRECT', text)
        for name in ('Clash-Windows.yaml', 'Clash-Windows-Campus.yaml'):
            dns = yaml.safe_load(artifacts[name])['dns']
            self.assertEqual(dns['nameserver-policy']['+.mesh.example.net'], ['100.100.100.100'])
            self.assertIn('+.mesh.example.net', dns['fake-ip-filter'])
            self.assertEqual(dns['nameserver-policy']['+.ts.net'], ['100.100.100.100'])

    def test_quad100_covers_all_ts_net_subdomains_without_tailnet_enumeration(self):
        data = copy.deepcopy(self.data)
        data['tailscale']['magic_domains'] = ['first.ts.net', 'second.ts.net', 'host.first.ts.net']
        artifacts = build(data)
        positive = ('ts.net', 'node.first.ts.net', 'node.second.ts.net', 'new.deep.third.ts.net')
        negative = ('notts.net', 'node.ts.net.example.com', 'tailscale.com')
        for name in ('Surge-Mac.conf', 'Surge-Macmini-Campus.conf', 'Surge-iOS.conf'):
            text = artifacts[name]
            hosts = assignments(section(text, 'Host')[2])
            quad100 = [h for h, server in hosts.items() if server == 'server:100.100.100.100']
            self.assertEqual(quad100, ['ts.net', '*.ts.net'])
            for domain in positive:
                self.assertTrue(any(fnmatch.fnmatchcase(domain, h) for h in quad100), domain)
            for domain in negative:
                self.assertFalse(any(fnmatch.fnmatchcase(domain, h) for h in quad100), domain)
            self.assertNotIn('first.ts.net', text)
            self.assertNotIn('second.ts.net', text)
        for name in ('Clash-Windows.yaml', 'Clash-Windows-Campus.yaml'):
            dns = yaml.safe_load(artifacts[name])['dns']
            self.assertEqual([h for h, servers in dns['nameserver-policy'].items()
                              if servers == ['100.100.100.100']], ['+.ts.net'])
            self.assertIn('+.ts.net', dns['fake-ip-filter'])

    def test_campus_dns_and_bypass_keep_domain_and_address_scopes_separate(self):
        data = copy.deepcopy(self.data)
        data['campus'].update(dns=['192.0.2.53'], extra_domains=['license.example.net'],
                              extra_cidrs=['203.0.113.32/27'])
        artifacts = build(data)
        text = artifacts['Surge-Macmini-Campus.conf']
        general = assignments(section(text, 'General')[2])
        hosts = assignments(section(text, 'Host')[2])
        for selector in ('pku.edu.cn', '*.pku.edu.cn', 'license.example.net', '*.license.example.net'):
            self.assertEqual(hosts[selector], 'server:192.0.2.53')
            self.assertIn(selector, general['always-real-ip'].split(', '))
            self.assertIn(selector, general['skip-proxy'].split(', '))
        self.assertIn('203.0.113.32/27', general['tun-excluded-routes'].split(', '))
        self.assertNotIn('*.wiley.com', general['skip-proxy'].split(', '))
        self.assertNotIn('198.18.0.0/15', general['tun-excluded-routes'].split(', '))
        windows = yaml.safe_load(artifacts['Clash-Windows-Campus.yaml'])
        self.assertEqual(windows['dns']['nameserver-policy']['+.pku.edu.cn'], ['192.0.2.53#DIRECT'])
        self.assertIn('+.license.example.net', windows['dns']['fake-ip-filter'])
        self.assertIn('203.0.113.32/27', windows['tun']['route-exclude-address'])
        normal = assignments(section(artifacts['Surge-Mac.conf'], 'General')[2])
        self.assertNotIn('162.105.0.0/16', normal['tun-excluded-routes'].split(', '))

    def test_campus_bypass_cannot_steal_vpn_or_fake_ip_routes(self):
        for route in ('100.64.0.0/10', '198.18.0.0/15', 'fc00::/7'):
            data = copy.deepcopy(self.data)
            data['campus']['extra_cidrs'] = [route]
            with self.assertRaisesRegex(ValueError, 'overlaps'):
                build(data)

    def test_desktop_control_dns_uses_direct_encryption_without_changing_private_dns(self):
        expected = ['https://223.5.5.5/dns-query', 'https://120.53.53.53/dns-query',
                    'tls://223.6.6.6', 'tls://1.12.12.12']
        for name in ('Surge-Mac.conf', 'Surge-Macmini-Campus.conf'):
            hosts = assignments(section(self.artifacts[name], 'Host')[2])
            for domain in CONTROL_DOMAINS:
                for selector in (domain, '*.' + domain):
                    self.assertEqual(hosts[selector], 'server:' + ','.join(expected))
            self.assertEqual(hosts['*.ts.net'], 'server:100.100.100.100')
        for name in ('Clash-Windows.yaml', 'Clash-Windows-Campus.yaml'):
            dns = yaml.safe_load(self.artifacts[name])['dns']
            for domain in CONTROL_DOMAINS:
                self.assertEqual(dns['nameserver-policy']['+.' + domain], [s + '#DIRECT' for s in expected])
            self.assertEqual(dns['nameserver-policy']['+.ts.net'], ['100.100.100.100'])
        campus_hosts = assignments(section(self.artifacts['Surge-Macmini-Campus.conf'], 'Host')[2])
        self.assertEqual(campus_hosts['*.pku.edu.cn'], 'server:system')
        self.assertEqual(yaml.safe_load(self.artifacts['Clash-Windows-Campus.yaml'])['dns']['nameserver-policy']['+.pku.edu.cn'], ['system'])

    def test_public_dns_keeps_encryption_and_certificate_verification(self):
        for name in ('Surge-Mac.conf', 'Surge-Macmini-Campus.conf', 'Surge-iOS.conf'):
            general = assignments(section(self.artifacts[name], 'General')[2])
            servers = [s.strip() for s in general['encrypted-dns-server'].split(',')]
            self.assertEqual(len(servers), 4)
            self.assertEqual(sum(s.startswith('https://') for s in servers), 2)
            self.assertEqual(sum(s.startswith('tls://') for s in servers), 2)
            self.assertEqual(general['encrypted-dns-skip-cert-verification'], 'false')
            self.assertEqual(general['encrypted-dns-follow-outbound-mode'], 'true')
        for name in ('Clash-Windows.yaml', 'Clash-Windows-Campus.yaml'):
            dns = yaml.safe_load(self.artifacts[name])['dns']
            for field in ('default-nameserver', 'proxy-server-nameserver', 'nameserver', 'direct-nameserver'):
                self.assertEqual(len(dns[field]), 4)
                self.assertEqual(sum(s.startswith('https://') for s in dns[field]), 2)
                self.assertEqual(sum(s.startswith('tls://') for s in dns[field]), 2)
                self.assertTrue(all('skip-cert-verify' not in s for s in dns[field]))
            self.assertEqual(dns['fallback'], [])

    def test_campus_overlay_after_reject_and_same_on_both_platforms(self):
        surge = section(self.artifacts['Surge-Macmini-Campus.conf'], 'Rule')[2].splitlines()
        clash = yaml.safe_load(self.artifacts['Clash-Windows-Campus.yaml'])['rules']
        for rule in campus_domains(self.data):
            expected = rule + ',DIRECT'
            self.assertIn(expected, surge)
            self.assertIn(expected, clash)
            self.assertGreater(clash.index(expected), clash.index('RULE-SET,Reject,REJECT'))
        standard = yaml.safe_load(self.artifacts['Clash-Windows.yaml'])['rules']
        self.assertNotIn('DOMAIN-SUFFIX,mathworks.com,DIRECT', standard)

    def test_actual_routing_positive_and_negative_witnesses(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'campus.conf'
            path.write_text(self.artifacts['Surge-Macmini-Campus.conf'])
            engine = Engine(str(path), str(ROOT / 'lists'))
            for host in ('sso.pku.edu.cn', 'licensing.mathworks.com', 'www.originlab.com',
                         'onlinelibrary.wiley.com', 'www.sciencedirect.com', 'www.webofscience.com',
                         'login.proquest.com', 'www.endnote.com'):
                self.assertEqual(engine.match(host=host, stage='domain')['policy'], 'DIRECT', host)
            for host in ('mathworks.com.example.invalid', 'evilpku.edu.cn.example.invalid', 'wiley.com.example.invalid'):
                # .invalid is intentionally owned by PrivateLAN in the base rules.
                self.assertEqual(engine.match(host=host, stage='domain')['source'], 'PrivateLAN.list', host)
            for address in ('162.105.134.153', '162.105.138.102', '2001:da8:201::1'):
                self.assertEqual(engine.match(ip=address)['policy'], 'DIRECT')

    def test_public_order_is_unchanged(self):
        routing = load_routing_manifest(str(ROOT / 'config/routing.json'), str(ROOT / 'lists'))
        expected = [r for r in render_rules(routing).splitlines() if r.startswith(('RULE-SET,', 'AND,', 'FINAL,'))]
        for name in ('Surge-Mac.conf', 'Surge-iOS.conf', 'Surge-Macmini-Campus.conf'):
            actual = [r for r in section(self.artifacts[name], 'Rule')[2].splitlines() if r.startswith(('RULE-SET,', 'AND,', 'FINAL,'))]
            self.assertEqual(actual, expected)

    def test_fail_closed_on_missing_campus_egress(self):
        data = copy.deepcopy(self.data)
        data['campus']['confirmed_on_campus'] = False
        with self.assertRaises(ValueError):
            build(data)

    def test_cycles_and_unapproved_processes_fail(self):
        for change in ('cycle', 'process'):
            data = copy.deepcopy(self.data)
            if change == 'cycle':
                data['groups'][0]['members'] = [data['groups'][0]['name']]
            else:
                data['tailscale']['mac_transport_processes'] = ['Browser']
                data['tailscale']['process_exception_reason'] = 'not a transport'
            with self.assertRaises(ValueError):
                validate_inventory(data)

    def test_private_files_cannot_enter_repository(self):
        with self.assertRaises(ValueError):
            private_path(ROOT / 'inventory.json')


if __name__ == '__main__':
    unittest.main()
