#!/usr/bin/env python3
"""公开设备覆盖层回归测试；仅使用公开源和中性临时样例，不读取私人配置。"""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import copy
import fnmatch
import hashlib
import io
import ipaddress
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import device_overlays as overlay
from rule_syntax import split_fields, unwrap

NAMES = {
    "TailscaleProxy", "TailscaleCampusProxy", "TailscaleControl", "TailscaleNetwork",
    "TailscaleNetworkIP", "CampusNetwork", "CampusNetworkIP", "CampusServices",
    "CloudflareTunnel", "CloudflareTunnelIP", "WindowsGateway", "WindowsGatewayPorts",
    "WindowsReject", "UKAI", "TailscaleWebsiteDNS", "CampusExtraIP",
}


def payload(text):
    return tuple(line for line in text.splitlines() if line and not line.startswith("#"))


def matches(rule, *, host="", address="", port=0, protocol="tcp"):
    """独立比对正反例；不做 DNS 查询，不代替实际客户端验证。"""
    fields = split_fields(rule)
    kind, value = fields[:2]
    if kind == "AND":
        return all(matches(unwrap(part), host=host, address=address, port=port, protocol=protocol)
                   for part in split_fields(unwrap(value)))
    if kind == "DOMAIN":
        return host == value
    if kind == "DOMAIN-SUFFIX":
        return host == value or host.endswith("." + value)
    if kind == "DOMAIN-WILDCARD":
        return fnmatch.fnmatchcase(host, value)
    if kind in {"IP-CIDR", "IP-CIDR6"}:
        return bool(address) and ipaddress.ip_address(address) in ipaddress.ip_network(value, strict=False)
    if kind in {"DEST-PORT", "DST-PORT"}:
        return port == int(value)
    if kind in {"PROTOCOL", "NETWORK"}:
        return protocol == value.lower()
    raise AssertionError("未覆盖的测试规则类型")


class DeviceOverlaysTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="overlay-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for relative in [overlay.MANIFEST, "config/campus-services.json", *overlay.COMMON_SOURCES]:
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, target)
        shutil.copytree(ROOT / "overlays/sources", self.root / "overlays/sources")
        self.manifest = json.loads((self.root / overlay.MANIFEST).read_text())

    def save_manifest(self):
        (self.root / overlay.MANIFEST).write_text(json.dumps(self.manifest), encoding="utf-8")

    def entry(self, name):
        return next(e for e in self.manifest["overlays"] if e["name"] == name)

    def append(self, relative, text):
        path = self.root / relative
        path.write_text(path.read_text() + text + "\n", encoding="utf-8")

    def build(self):
        return overlay.build(self.root)

    def rules(self, name, client="surge"):
        return payload(self.build()[f"overlays/{client}/{name}.list"])

    def invalid(self):
        with self.assertRaises(overlay.OverlayError):
            self.build()

    def test_output_contract(self):
        artifacts = self.build()
        expected = {f"overlays/{client}/{name}.list" for client in ("surge", "clash") for name in NAMES}
        expected |= {"overlays/index.json", "overlays/clash/rule-providers.yaml"}
        self.assertEqual(expected, set(artifacts))
        self.assertEqual(artifacts, self.build())
        index = json.loads(artifacts["overlays/index.json"])
        self.assertEqual(NAMES, {e["name"] for e in index["overlays"]})
        for path, digest in index["inputs"].items():
            self.assertFalse(Path(path).is_absolute())
            self.assertEqual(hashlib.sha256((self.root / path).read_bytes()).hexdigest(), digest)
        for entry in index["overlays"]:
            self.assertEqual(entry["rule_count"], len(payload(artifacts[entry["surge"]["path"]])))
            for client in ("surge", "clash"):
                self.assertEqual(overlay.CDN_BASE + "/" + entry[client]["path"], entry[client]["url"])

    def test_common_manifest_unchanged_and_disjoint(self):
        common = json.loads((ROOT / "config/routing.json").read_text())
        self.assertEqual(53, len(common["rulesets"]))
        self.assertFalse(NAMES & {e["name"] for e in common["rulesets"]})
        self.assertTrue(all(path.startswith("overlays/") for path in self.build()))
        self.assertNotIn("config/routing.json", json.loads(self.build()["overlays/index.json"])["inputs"])

    def test_check_and_rebuild_are_read_only_when_current(self):
        artifacts = self.build()
        overlay.write_artifacts(artifacts, self.root)
        paths = [self.root / path for path in artifacts]
        before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in paths}
        self.assertEqual(([], []), overlay.drift(artifacts, self.root))
        self.assertEqual([], overlay.write_artifacts(artifacts, self.root))
        with patch.object(overlay, "ROOT", self.root), redirect_stdout(io.StringIO()):
            self.assertEqual(0, overlay.main(["--check"]))
        self.assertEqual(before, {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in paths})

    def test_check_detects_drift_without_writing(self):
        artifacts = self.build()
        overlay.write_artifacts(artifacts, self.root)
        target = self.root / "overlays/clash/UKAI.list"
        target.write_text("# changed\n", encoding="utf-8")
        stamp = target.stat().st_mtime_ns
        with patch.object(overlay, "ROOT", self.root), redirect_stdout(io.StringIO()):
            self.assertEqual(1, overlay.main(["--check"]))
        self.assertEqual("# changed\n", target.read_text())
        self.assertEqual(stamp, target.stat().st_mtime_ns)

    def test_unexpected_generated_file_is_not_deleted(self):
        artifacts = self.build()
        overlay.write_artifacts(artifacts, self.root)
        extra = self.root / "overlays/clash/Extra.list"
        extra.write_text("# concurrent work\n", encoding="utf-8")
        self.assertEqual(["overlays/clash/Extra.list"], overlay.drift(artifacts, self.root)[1])
        with self.assertRaises(overlay.OverlayError):
            overlay.write_artifacts(artifacts, self.root)
        self.assertTrue(extra.exists())

    def test_unexpected_overlay_root_file_is_reported(self):
        artifacts = self.build()
        path = self.root / "overlays/unreviewed.txt"
        path.write_text("neutral diagnostic marker\n", encoding="utf-8")
        self.assertEqual(["overlays/unreviewed.txt"], overlay.drift(artifacts, self.root)[1])
        with self.assertRaises(overlay.OverlayError):
            overlay.write_artifacts(artifacts, self.root)
        self.assertTrue(path.exists())

    def test_concurrent_source_edit_aborts_build(self):
        original = overlay.compose

        def changed(root):
            result = original(root)
            self.append("lists/Academic.list", "# concurrent public edit")
            return result

        with patch.object(overlay, "compose", side_effect=changed):
            self.invalid()

    def test_validation_failure_does_not_replace_outputs(self):
        artifacts = self.build()
        overlay.write_artifacts(artifacts, self.root)
        self.append("overlays/sources/TailscaleProxy.list", "UNSUPPORTED,example.com")
        with patch.object(overlay, "ROOT", self.root), redirect_stderr(io.StringIO()):
            self.assertEqual(2, overlay.main([]))
        for path, text in artifacts.items():
            self.assertEqual(text.encode(), (self.root / path).read_bytes())

    def test_composed_website_dependency_propagates(self):
        old = self.build()
        self.append("overlays/sources/TailscaleProxy.list", "DOMAIN,new-public-page.tailscale.com")
        new = self.build()
        changed = {p for p in old if old[p] != new[p]}
        self.assertEqual({"overlays/index.json"} | {
            f"overlays/{c}/{n}.list" for c in ("surge", "clash") for n in ("TailscaleProxy", "TailscaleCampusProxy")}, changed)

    def test_pku_and_academic_dependencies_propagate(self):
        old = self.build()
        self.append("lists/PKU.list", "DOMAIN-SUFFIX,new-service.pku.edu.cn")
        self.append("lists/Academic.list", "DOMAIN,reviewed.example.org")
        new = self.build()
        for client in ("surge", "clash"):
            network = payload(new[f"overlays/{client}/CampusNetwork.list"])
            services = payload(new[f"overlays/{client}/CampusServices.list"])
            self.assertIn("DOMAIN-SUFFIX,new-service.pku.edu.cn", network)
            self.assertIn("DOMAIN-SUFFIX,new-service.pku.edu.cn", services)
            self.assertIn("DOMAIN,reviewed.example.org", services)
            self.assertEqual(old[f"overlays/{client}/UKAI.list"], new[f"overlays/{client}/UKAI.list"])

    def test_requested_pku_addition_is_derived_not_copied(self):
        rule = "DOMAIN-SUFFIX,pku-dasys.cn"
        if rule not in (self.root / "lists/PKU.list").read_text().splitlines():
            self.append("lists/PKU.list", rule)
        for name in ("CampusNetwork", "CampusServices"):
            for client in ("surge", "clash"):
                self.assertIn(rule, self.rules(name, client))
        self.assertFalse(any("pku-dasys.cn" in p.read_text() for p in (self.root / "overlays/sources").glob("*.list")))

    def test_campus_json_dependency_propagates(self):
        path = self.root / "config/campus-services.json"
        data = json.loads(path.read_text())
        data["families"][0]["suffixes"].append("reviewed.example.org")
        path.write_text(json.dumps(data), encoding="utf-8")
        self.assertIn("DOMAIN-SUFFIX,reviewed.example.org", self.rules("CampusServices"))
        self.assertNotIn("DOMAIN-SUFFIX,reviewed.example.org", self.rules("CampusNetwork"))

    def test_pkuip_dependency_and_no_resolve_propagate(self):
        self.append("lists/PKUIP.list", "IP-CIDR,162.105.1.1/32")
        for client in ("surge", "clash"):
            rules = self.rules("CampusNetworkIP", client)
            self.assertIn("IP-CIDR,162.105.1.1/32,no-resolve", rules)
            self.assertIn("IP-CIDR,10.129.167.101/32,no-resolve", rules)
            self.assertTrue(all(r.endswith(",no-resolve") for r in rules))

    def test_campus_is_derived_without_duplicate_maintenance(self):
        sources = self.entry("CampusServices")["sources"]
        self.assertEqual(["overlay", "common", "campus-services"], [s["type"] for s in sources])
        expected = list(self.rules("CampusNetwork"))
        expected += [line for line in (self.root / "lists/Academic.list").read_text().splitlines() if line.startswith("DOMAIN")]
        for family in json.loads((self.root / "config/campus-services.json").read_text())["families"]:
            expected += ["DOMAIN-SUFFIX," + s for s in family["suffixes"]]
        self.assertEqual(tuple(dict.fromkeys(expected)), self.rules("CampusServices"))
        self.assertFalse((self.root / "overlays/sources/CampusServices.list").exists())
        self.assertFalse((self.root / "overlays/sources/CampusNetwork.list").exists())

    def test_transitive_exact_deduplication(self):
        duplicate = self.rules("CampusNetwork")[0]
        self.append("lists/Academic.list", duplicate)
        self.assertEqual(1, self.rules("CampusServices").count(duplicate))

    def test_tailscale_website_and_relay_boundaries(self):
        common = self.rules("TailscaleProxy")
        campus = self.rules("TailscaleCampusProxy")
        self.assertEqual(13, len(common))
        self.assertEqual(19, len(campus))
        self.assertEqual(common, campus[:13])
        self.assertTrue(all(r.startswith("DOMAIN,") for r in common))
        positives = ("derp10.tailscale.com", "derpab.tailscale.com", "derp27e.tailscale.com")
        negatives = ("derp1.tailscale.com", "derp123.tailscale.com", "derp99a.tailscale.com", "derp10.tailscale.com.example.org")
        for host in positives:
            self.assertFalse(any(matches(r, host=host) for r in common))
            self.assertTrue(any(matches(r, host=host) for r in campus))
        for host in negatives:
            self.assertFalse(any(matches(r, host=host) for r in campus))
        self.assertFalse(any(matches(r, host="controlplane.tailscale.com") for r in common))
        self.assertTrue(any(matches(r, host="controlplane.tailscale.com") for r in self.rules("TailscaleControl")))

    def test_control_network_and_tunnel_scope_snapshots(self):
        self.assertEqual(("DOMAIN-SUFFIX,tailscale.com", "DOMAIN-SUFFIX,tailscale.io", "DOMAIN-SUFFIX,tailscale.net"),
                         self.rules("TailscaleControl"))
        self.assertEqual(("DOMAIN-SUFFIX,ts.net",), self.rules("TailscaleNetwork"))
        self.assertEqual(("IP-CIDR,100.64.0.0/10,no-resolve", "IP-CIDR6,fd7a:115c:a1e0::/48,no-resolve"),
                         self.rules("TailscaleNetworkIP"))
        self.assertEqual(("DOMAIN-SUFFIX,argotunnel.com",), self.rules("CloudflareTunnel"))
        for name in ("CampusNetwork", "CampusServices", "CampusNetworkIP"):
            self.assertEqual("after-reject", self.entry(name)["placement"])

    def test_selection_order_conflicts_and_intended_clients(self):
        names = [e["name"] for e in overlay.ordered_selection(
            ["TailscaleControl", "TailscaleCampusProxy", "CampusServices", "CampusNetwork"], "surge-macos", self.root)]
        self.assertEqual(["TailscaleCampusProxy", "TailscaleControl", "CampusNetwork", "CampusServices"], names)
        for selected, client in [(["TailscaleProxy", "TailscaleCampusProxy"], "surge-macos"),
                                  (["TailscaleCampusProxy"], "surge-ios"), (["UKAI"], "mihomo-windows"),
                                  (["Unknown"], "surge-macos"), (["UKAI", "UKAI"], "surge-macos")]:
            with self.subTest(selected=selected), self.assertRaises(overlay.OverlayError):
                overlay.ordered_selection(selected, client, self.root)
        self.assertEqual(["TailscaleCampusProxy"], [e["name"] for e in overlay.ordered_selection(
            ["TailscaleCampusProxy"], "surge-macos", self.root)])

    def test_bindings_do_not_embed_private_policy(self):
        self.assertEqual("RULE-SET," + overlay.CDN_BASE + "/overlays/surge/TailscaleNetworkIP.list,DIRECT,no-resolve",
                         overlay.render_call("TailscaleNetworkIP", "DIRECT", root=self.root))
        self.assertEqual("RULE-SET,DeviceOverlayUKAI,ExamplePolicy",
                         overlay.render_call("UKAI", "ExamplePolicy", mihomo=True, root=self.root))
        for policy in ("", "x,y", "x\nFINAL,DIRECT", " x", "x#y"):
            with self.assertRaises(overlay.OverlayError):
                overlay.render_call("UKAI", policy, root=self.root)
        self.assertNotIn("ExamplePolicy", "".join(self.build().values()))

    def test_provider_metadata_is_optional_and_policy_free(self):
        providers = self.build()["overlays/clash/rule-providers.yaml"]
        self.assertEqual(len(NAMES), providers.count("    behavior: classical\n"))
        self.assertEqual(len(NAMES), providers.count("    format: text\n"))
        self.assertEqual(len(NAMES), providers.count("    interval: 86400\n"))
        self.assertEqual(("DOMAIN,tailscale.com", "DOMAIN,www.tailscale.com",
                          "DOMAIN,login.tailscale.com", "DOMAIN,console.tailscale.com"),
                         self.rules("TailscaleWebsiteDNS"))
        self.assertNotIn("\nrules:", providers)
        self.assertNotIn("\ndns:", providers)
        for name in NAMES:
            self.assertIn(f"  DeviceOverlay{name}:\n", providers)
            self.assertIn(f"@main/overlays/clash/{name}.list", providers)
            self.assertIn(f"./rule-sets/surge-rules/device-overlays/v1/{name}.list", providers)

    def test_cloudflare_conjunction_conversion_and_effective_intervals(self):
        source = self.rules("CloudflareTunnelIP")
        target = self.rules("CloudflareTunnelIP", "clash")
        self.assertEqual(3, len(source))
        self.assertEqual(source, tuple(r.replace("DST-PORT", "DEST-PORT") for r in target))
        self.assertEqual(ipaddress.ip_network("2606:4700:a0::/44"),
                         ipaddress.ip_network("2606:4700:a8::/44", strict=False))
        inside = ["198.41.192.0", "198.41.223.255", "2606:4700:a0::", "2606:4700:af:ffff:ffff:ffff:ffff:ffff"]
        outside = ["198.41.191.255", "198.41.224.0", "2606:4700:9f:ffff::1", "2606:4700:b0::", "1.1.1.1"]
        for address in inside + outside:
            for port in (7844, 443, 7843, 7845):
                for protocol in ("tcp", "udp"):
                    with self.subTest(address=address, port=port, protocol=protocol):
                        expected = address in inside and port == 7844
                        for rules in (source, target):
                            self.assertEqual(expected, any(matches(r, address=address, port=port, protocol=protocol) for r in rules))
        self.assertTrue(all(",no-resolve)" in rule for rule in source + target))

    def test_windows_ports_preserve_protocol_constraint(self):
        source = self.rules("WindowsGatewayPorts")
        target = self.rules("WindowsGatewayPorts", "clash")
        self.assertEqual(("AND,((PROTOCOL,UDP),(DEST-PORT,123))", "DEST-PORT,7680"), source)
        self.assertEqual(("AND,((NETWORK,udp),(DST-PORT,123))", "DST-PORT,7680"), target)
        for port in (123, 7680, 443, 80):
            for protocol in ("udp", "tcp"):
                expected = port == 7680 or (port == 123 and protocol == "udp")
                for rules in (source, target):
                    self.assertEqual(expected, any(matches(r, port=port, protocol=protocol) for r in rules))

    def test_windows_domain_controls_not_broadened(self):
        self.assertEqual(("DOMAIN-SUFFIX,do.dsp.mp.microsoft.com", "DOMAIN-SUFFIX,msftncsi.com", "DOMAIN,get.microsoft.com"), self.rules("WindowsGateway"))
        self.assertEqual(("DOMAIN-SUFFIX,ipv6.microsoft.com",), self.rules("WindowsReject"))
        for host in ("microsoft.com", "www.get.microsoft.com", "msftconnecttest.com"):
            self.assertFalse(any(matches(r, host=host) for r in self.rules("WindowsGateway")))

    def test_uk_exception_snapshot_order_and_types(self):
        expected = """DOMAIN-SUFFIX,gemini.google.com
DOMAIN-SUFFIX,gemini.google
DOMAIN-SUFFIX,aistudio.google.com
DOMAIN-SUFFIX,makersuite.google.com
DOMAIN,alkalimakersuite-pa.clients6.google.com
DOMAIN-SUFFIX,generativelanguage.googleapis.com
DOMAIN-SUFFIX,notebooklm.google.com
DOMAIN-SUFFIX,notebooklm.google
DOMAIN-SUFFIX,labs.google
DOMAIN,aisandbox-pa.googleapis.com
DOMAIN-SUFFIX,jules.google.com
DOMAIN-SUFFIX,jules.google
DOMAIN-SUFFIX,antigravity.google
DOMAIN,cloudcode-pa.googleapis.com
DOMAIN,daily-cloudcode-pa.googleapis.com
DOMAIN-SUFFIX,aiplatform.googleapis.com
DOMAIN-WILDCARD,*-aiplatform.googleapis.com
DOMAIN-SUFFIX,gemini-api-docs-mcp.dev
DOMAIN-SUFFIX,copilot.microsoft.com
DOMAIN-SUFFIX,copilot.com
DOMAIN-SUFFIX,copilot.cloud.microsoft
DOMAIN-SUFFIX,m365copilot.com
DOMAIN,copilotprodattachments.blob.core.windows.net
DOMAIN,sydney.bing.com
DOMAIN-SUFFIX,githubcopilot.com
DOMAIN,copilot-proxy.githubusercontent.com
DOMAIN-SUFFIX,meta.ai
DOMAIN-SUFFIX,llama.com
DOMAIN-SUFFIX,grok.com
DOMAIN-SUFFIX,x.ai"""
        self.assertEqual(tuple(expected.splitlines()), self.rules("UKAI"))
        self.assertEqual(self.rules("UKAI"), self.rules("UKAI", "clash"))
        self.assertEqual("uk-ai-exceptions", self.entry("UKAI")["placement"])
        for host in ("storage.googleapis.com", "githubusercontent.com", "blob.core.windows.net", "bing.com", "google.com"):
            self.assertFalse(any(matches(r, host=host) for r in self.rules("UKAI")))
        self.assertTrue(any(matches(r, host="us-central1-aiplatform.googleapis.com") for r in self.rules("UKAI")))

    def test_no_quic_block_or_private_rule_types_in_payloads(self):
        for path, text in self.build().items():
            if not path.endswith(".list"):
                continue
            for rule in payload(text):
                self.assertNotIn("443", rule)
                for forbidden in ("PROCESS", "SRC-", "SOURCE", "IN-PORT", "USER-AGENT", "URL-REGEX", "QUIC", "REJECT", "DIRECT"):
                    self.assertNotIn(forbidden, rule)
                self.assertFalse(rule.startswith("PROTOCOL,"))
                self.assertFalse(rule.startswith("NETWORK,"))

    def test_no_private_input_paths_or_comment_leaks_in_outputs(self):
        marker = "SYNTHETIC_PRIVATE_COMMENT_NOT_FOR_EXPORT"
        self.append("overlays/sources/TailscaleProxy.list", "# " + marker)
        artifacts = self.build()
        for text in artifacts.values():
            for forbidden in (str(self.root), marker, "/Users/", "/baseline/", "/archive/", "client-source", "password="):
                self.assertNotIn(forbidden, text)
        for entry in json.loads(artifacts["overlays/index.json"])["overlays"]:
            self.assertTrue(all(not Path(p).is_absolute() for p in entry["inputs"]))

    def test_schema_rejects_unknown_and_missing_fields(self):
        original = copy.deepcopy(self.manifest)
        for mutate in (
            lambda d: d.update(extra=True),
            lambda d: d.update(version=True),
            lambda d: d["overlays"][0].update(policy="DIRECT"),
            lambda d: d["overlays"][0].pop("reason"),
            lambda d: d["overlays"][0].update(reason=""),
            lambda d: d["overlays"][0].update(kind="mixed"),
            lambda d: d["overlays"][0].update(clients=["unknown"]),
            lambda d: d["overlays"][0].update(clients=["surge-macos", "surge-macos"]),
            lambda d: d["overlays"][0].update(placement="unknown"),
            lambda d: d["overlays"][0]["sources"][0].update(secret="x"),
        ):
            self.manifest = copy.deepcopy(original)
            mutate(self.manifest)
            self.save_manifest()
            self.invalid()

    def test_duplicate_json_keys_and_names(self):
        path = self.root / overlay.MANIFEST
        path.write_text('{"version":1,"version":1,"overlays":[]}', encoding="utf-8")
        self.invalid()
        self.manifest["overlays"].append(copy.deepcopy(self.manifest["overlays"][0]))
        self.save_manifest()
        self.invalid()

    def test_invalid_graphs_and_order_fail_closed(self):
        original = copy.deepcopy(self.manifest)
        def website(d):
            return next(e for e in d["overlays"] if e["name"] == "TailscaleProxy")
        for mutate in (
            lambda d: website(d)["sources"].append({"type": "overlay", "name": "TailscaleCampusProxy"}),
            lambda d: website(d)["sources"].append({"type": "overlay", "name": "Unknown"}),
            lambda d: website(d)["sources"].append({"type": "overlay", "name": "TailscaleNetworkIP"}),
            lambda d: d["overlays"].reverse(),
            lambda d: website(d).update(conflicts=[]),
        ):
            self.manifest = copy.deepcopy(original)
            mutate(self.manifest)
            self.save_manifest()
            self.invalid()

    def test_forbidden_source_paths_and_symlinks(self):
        source = self.entry("TailscaleProxy")["sources"][0]
        for path in ("/tmp/example.list", "../private.list", "overlays/sources/../private.list",
                     "overlays//sources/Example.list", "clash/AI.list", "C:\\private.list", "overlays/sources/Extra.txt"):
            source["path"] = path
            self.save_manifest()
            self.invalid()
        source["path"] = "overlays/sources/TailscaleProxy.list"
        self.save_manifest()
        path = self.root / source["path"]
        path.unlink()
        path.symlink_to(self.root / "lists/PKU.list")
        self.invalid()

    def test_symlinked_output_or_unused_directory_fails(self):
        artifacts = self.build()
        path = self.root / "overlays/surge"
        path.symlink_to(self.root / "lists", target_is_directory=True)
        with self.assertRaises(overlay.OverlayError):
            overlay.drift(artifacts, self.root)
        path.unlink()
        path = self.root / "overlays/sources/unreviewed"
        path.symlink_to(self.root / "lists", target_is_directory=True)
        self.invalid()

    def test_unreferenced_curated_source_fails(self):
        (self.root / "overlays/sources/Unreviewed.list").write_text("DOMAIN,example.com\n", encoding="utf-8")
        self.invalid()

    def test_unsupported_rules_policies_and_private_selectors_fail(self):
        path = self.root / "overlays/sources/TailscaleProxy.list"
        original = path.read_text()
        bad = ["PROCESS-NAME,example-helper", "SRC-IP,192.0.2.10", "IP-SRC,192.0.2.10",
               "SOURCE-IP-CIDR,192.0.2.0/24", "IN-PORT,8080", "USER-AGENT,Example",
               "URL-REGEX,example", "GEOIP,CN", "IP-ASN,1", "RULE-SET,example.list",
               "FINAL", "DOMAIN,tailscale.com,DIRECT", "DOMAIN-SUFFIX,private.example.org",
               "DOMAIN,192.0.2.1", "DOMAIN,peer.private.ts.net", "DOMAIN,host.local",
               "AND,((PROTOCOL,QUIC),(DEST-PORT,443))", "OR,((DOMAIN,tailscale.com),(DOMAIN,example.com))"]
        for rule in bad:
            with self.subTest(rule=rule):
                path.write_text(original + rule + "\n", encoding="utf-8")
                self.invalid()

    def test_private_networks_cannot_be_admitted_by_manifest_scope(self):
        source = self.entry("TailscaleNetworkIP")["sources"][0]
        for cidr in ("10.0.0.0/8", "100.64.1.2/32", "fd7a:115c:a1e0::1/128", "198.18.0.0/15", "127.0.0.1/32", "224.0.0.0/4"):
            source["cidrs"] = [cidr]
            self.save_manifest()
            self.invalid()

    def test_ip_modifiers_ports_and_canonical_shape_fail_closed(self):
        path = self.root / "overlays/sources/CloudflareTunnelIP.list"
        for rule in ("IP-CIDR,198.41.192.0/19,no-resolve", "AND,((DEST-PORT,443),(IP-CIDR,198.41.192.0/19,no-resolve))",
                     "AND,((DEST-PORT,7844),(IP-CIDR,198.41.192.0/19))",
                     "AND,((DEST-PORT,7844),(IP-CIDR,198.41.192.0/18,no-resolve))",
                     "AND,((DEST-PORT,7844),(IP-CIDR,198.41.192.1/19,no-resolve))",
                     "AND,((DEST-PORT,7844),(IP-CIDR6,198.41.192.0/19,no-resolve))",
                     "AND,((DEST-PORT,7844),(IP-CIDR,198.41.192.0/19,DIRECT,no-resolve))",
                     "AND,((DEST-PORT,7844),(IP-CIDR,198.41.192.0/19,no-resolve)),DIRECT"):
            with self.subTest(rule=rule):
                path.write_text(rule + "\n", encoding="utf-8")
                self.invalid()

    def test_transport_rejects_unconstrained_protocol_and_quic(self):
        path = self.root / "overlays/sources/WindowsGatewayPorts.list"
        for rule in ("PROTOCOL,UDP", "AND,((PROTOCOL,QUIC),(DEST-PORT,123))",
                     "AND,((PROTOCOL,UDP),(DEST-PORT,443))", "DEST-PORT,0", "DEST-PORT,65536",
                     "AND,((PROTOCOL,UDP),(DEST-PORT,123),(DEST-PORT,7680))",
                     "AND,((PROTOCOL,UDP),(NOT,((DEST-PORT,123)))))"):
            path.write_text(rule + "\n", encoding="utf-8")
            self.invalid()

    def test_duplicate_empty_and_mixed_sources_fail(self):
        path = self.root / "overlays/sources/TailscaleProxy.list"
        for text in ("# empty\n", "DOMAIN,tailscale.com\nDOMAIN,tailscale.com\n", "IP-CIDR,1.1.1.1/32,no-resolve\n"):
            path.write_text(text, encoding="utf-8")
            self.invalid()

    def test_campus_schema_and_private_namespace_fail_closed(self):
        path = self.root / "config/campus-services.json"
        original = json.loads(path.read_text())
        for change in ("unknown", "private", "policy", "absolute-evidence"):
            data = copy.deepcopy(original)
            if change == "unknown":
                data["families"][0]["extra"] = True
            elif change == "private":
                data["families"][0]["suffixes"].append("peer.private.ts.net")
            elif change == "policy":
                data["families"][0]["suffixes"].append("example.org,DIRECT")
            else:
                data["families"][0]["evidence"] = ["/tmp/private-evidence"]
            path.write_text(json.dumps(data), encoding="utf-8")
            self.invalid()

    def test_uk_wildcard_scope_does_not_admit_other_api_hosts(self):
        self.append("overlays/sources/UKAI.list", "DOMAIN,unreviewed.googleapis.com")
        self.invalid()


if __name__ == "__main__":
    unittest.main(verbosity=2)
