#!/usr/bin/env python3
"""Build optional, policy-free device overlays without changing common routing.

The only composition manifest is config/device-overlays.json. No private profile
is an input. Build/check is offline; --native additionally checks temporary Surge
inline rulesets and local Mihomo classical providers, without starting a client.
"""
from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile

from rule_syntax import split_fields, unwrap

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = "config/device-overlays.json"
CDN_BASE = "https://cdn.jsdelivr.net/gh/yhyfhgs/surge-rules@main"
CLIENTS = {"surge-macos", "surge-ios", "mihomo-windows"}
KINDS = {"domain", "ip", "transport"}
PLACEMENTS = {"before-common", "after-reject", "uk-ai-exceptions"}
DOMAIN_TYPES = {"DOMAIN", "DOMAIN-SUFFIX", "DOMAIN-WILDCARD"}
IP_TYPES = {"IP-CIDR", "IP-CIDR6"}
COMMON_SOURCES = {"lists/PKU.list": "domain", "lists/Academic.list": "domain",
                  "lists/PKUIP.list": "ip"}
# Public protocol allocations and the one owner-approved campus destination.
# Never allow a general private range or an individual tailnet peer here.
NON_GLOBAL = {"100.64.0.0/10", "fd7a:115c:a1e0::/48", "10.129.167.101/32"}
NAME = re.compile(r"[A-Za-z][A-Za-z0-9]*\Z")
LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\Z")


class OverlayError(ValueError):
    """Invalid public input; errors deliberately omit untrusted rule values."""


def _require(condition, message):
    if not condition:
        raise OverlayError(message)


def _fields(value, required, optional=()):
    _require(isinstance(value, dict) and set(required) <= set(value)
             and set(value) <= set(required) | set(optional), "invalid object fields")


def _strings(value, *, empty=False):
    _require(isinstance(value, list) and (empty or bool(value))
             and all(isinstance(v, str) and v and v == v.strip() for v in value),
             "expected a list of nonempty strings")
    _require(len(set(value)) == len(value), "duplicate list item")
    return value


def _text(value):
    _require(isinstance(value, str) and bool(value.strip()) and value == value.strip()
             and value.isascii() and all(32 <= ord(c) < 127 for c in value),
             "expected nonempty single-line English metadata")


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def _path(root, relative):
    _require(isinstance(relative, str) and bool(relative), "invalid source path")
    p = PurePosixPath(relative)
    _require(not p.is_absolute() and str(p) == relative
             and all(part not in {".", ".."} for part in p.parts)
             and "\\" not in relative and ":" not in relative,
             "source paths must be normalized repository-relative paths")
    path = Path(root)
    for part in p.parts:
        path = path / part
        _require(not path.is_symlink(), "symlink inputs/outputs are forbidden")
    return path


def _read(root, relative):
    path = _path(root, relative)
    _require(path.is_file(), "missing public source file")
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise OverlayError("cannot read public source") from exc


def _json(root, relative):
    try:
        return json.loads(_read(root, relative), object_pairs_hook=_pairs)
    except (ValueError, RecursionError) as exc:
        raise OverlayError("invalid public JSON source") from exc


def _domain(value, wildcard=False):
    _require(isinstance(value, str) and 0 < len(value) <= 253
             and value == value.lower(), "invalid domain selector")
    plain = value.replace("*", "a").replace("?", "a") if wildcard else value
    labels = plain.split(".")
    _require(len(labels) >= 2 and all(LABEL.fullmatch(v) for v in labels)
             and not labels[-1].isdigit(), "invalid public domain selector")
    _require(labels[-1] not in {"local", "localhost", "internal", "lan", "home", "invalid"}
             and not plain.endswith(".home.arpa"), "private namespace forbidden")
    _require(plain == "ts.net" or not plain.endswith(".ts.net"),
             "individual tailnet namespaces are private")


def _network(value, version):
    try:
        # A reviewed legacy Cloudflare selector has host bits. Preserve its
        # spelling and effective masked set; do not expand or silently drop it.
        network = ipaddress.ip_network(value, strict=False)
        address, prefix = value.split("/")
        interface = ipaddress.ip_address(address)
        _require(network.version == version and str(interface) == address
                 and str(int(prefix)) == prefix, "invalid CIDR spelling or family")
        _require((network.is_global and not network.is_multicast and not network.is_reserved)
                 or value in NON_GLOBAL, "private/reserved infrastructure CIDR forbidden")
        _require(str(network) == value or value == "2606:4700:a8::/44",
                 "noncanonical CIDR forbidden")
        return network
    except ValueError as exc:
        raise OverlayError("invalid or unapproved destination CIDR") from exc


def parse_rule(text, kind, *, add_no_resolve=False):
    """Return canonical policy-free Surge syntax, accepting only portable forms.

    Logical rules are limited to a port AND one IP/protocol leaf. A parser that
    accepts arbitrary Surge rules would accidentally export device/process or
    source-address guards. No such fallback exists here.
    """
    _require(isinstance(text, str) and text and len(text) < 2048
             and not any(c in text for c in "\r\n#;\"'"), "invalid policy-free rule")
    try:
        parts = split_fields(text)
    except ValueError as exc:
        raise OverlayError("invalid logical rule") from exc
    rtype = parts[0]
    if rtype in DOMAIN_TYPES:
        _require(kind == "domain" and len(parts) == 2, "domain kind/policy mismatch")
        _domain(parts[1], rtype == "DOMAIN-WILDCARD")
        if rtype == "DOMAIN-WILDCARD":
            _require("*" in parts[1] or "?" in parts[1], "wildcard needs a wildcard")
        return ",".join(parts)
    if rtype in IP_TYPES:
        _require(kind == "ip" and (len(parts) == 3 or (add_no_resolve and len(parts) == 2)),
                 "IP rules require native no-resolve and no policy")
        _require(len(parts) == 2 or parts[2] == "no-resolve", "unsupported IP modifier")
        _network(parts[1], 4 if rtype == "IP-CIDR" else 6)
        return ",".join(parts[:2] + ["no-resolve"])
    if rtype == "DEST-PORT":
        _require(kind == "transport" and len(parts) == 2 and parts[1].isascii()
                 and parts[1].isdigit() and str(int(parts[1])) == parts[1]
                 and 1 <= int(parts[1]) <= 65535, "invalid destination port rule")
        return ",".join(parts)
    if rtype == "PROTOCOL":
        _require(kind == "transport" and len(parts) == 2 and parts[1] in {"TCP", "UDP"},
                 "unsupported protocol selector")
        return ",".join(parts)
    if rtype == "AND":
        _require(kind in {"ip", "transport"} and len(parts) == 2, "invalid logical kind/policy")
        try:
            operands = [unwrap(v) for v in split_fields(unwrap(parts[1]))]
        except ValueError as exc:
            raise OverlayError("invalid logical operands") from exc
        _require(len(operands) == 2, "logical rule requires exactly two leaves")
        leaves = []
        for operand in operands:
            leaf_type = operand.split(",", 1)[0].strip()
            _require(leaf_type in IP_TYPES | {"DEST-PORT", "PROTOCOL"},
                     "unsupported logical leaf")
            leaves.append(parse_rule(operand, "ip" if leaf_type in IP_TYPES else "transport",
                                     add_no_resolve=add_no_resolve))
        types = {leaf.split(",")[0] for leaf in leaves}
        expected = ({"DEST-PORT", "IP-CIDR"}, {"DEST-PORT", "IP-CIDR6"}) if kind == "ip" else ({"DEST-PORT", "PROTOCOL"},)
        _require(types in expected, "logical rule must constrain a port with an IP or protocol")
        return "AND,(" + ",".join("(" + leaf + ")" for leaf in leaves) + ")"
    raise OverlayError("unsupported public rule type")


def _leaves(rule):
    parts = split_fields(rule)
    if parts[0] == "AND":
        return [split_fields(unwrap(p)) for p in split_fields(unwrap(parts[1]))]
    return [parts]


def to_mihomo(rule):
    """Translate only already validated policy-free Surge syntax."""
    parts = split_fields(rule)
    if parts[0] == "AND":
        return "AND,(" + ",".join("(" + to_mihomo(unwrap(p)) + ")"
                                  for p in split_fields(unwrap(parts[1]))) + ")"
    if parts[0] == "DEST-PORT":
        return "DST-PORT," + parts[1]
    if parts[0] == "PROTOCOL":
        return "NETWORK," + parts[1].lower()
    _require(parts[0] in DOMAIN_TYPES | IP_TYPES, "unsupported conversion")
    return rule


def _validate_source(source, kind, root):
    _require(isinstance(source, dict), "invalid source")
    stype = source.get("type")
    if stype == "overlay":
        _fields(source, {"type", "name"})
        _require(isinstance(source["name"], str) and NAME.fullmatch(source["name"]),
                 "invalid overlay dependency")
    elif stype == "common":
        _fields(source, {"type", "path"})
        _require(isinstance(source["path"], str) and COMMON_SOURCES.get(source["path"]) == kind,
                 "unapproved common dependency or kind")
        _path(root, source["path"])
    elif stype == "campus-services":
        _fields(source, {"type", "path"})
        _require(kind == "domain" and source["path"] == "config/campus-services.json",
                 "invalid campus dependency")
        _path(root, source["path"])
    elif stype == "file":
        _fields(source, {"type", "path", "public_suffixes", "cidrs", "ports"})
        _path(root, source["path"])
        _require(re.fullmatch(r"overlays/sources/[A-Za-z][A-Za-z0-9]*\.list", source["path"]),
                 "curated sources must be in overlays/sources")
        for domain in _strings(source["public_suffixes"], empty=True):
            _domain(domain, wildcard=True)
        for cidr in _strings(source["cidrs"], empty=True):
            _network(cidr, 6 if ":" in cidr else 4)
        ports = source["ports"]
        _require(isinstance(ports, list) and all(type(p) is int and 1 <= p <= 65535 for p in ports)
                 and len(set(ports)) == len(ports), "invalid public port scope")
        _require((kind == "domain" and bool(source["public_suffixes"]) and not source["cidrs"] and not ports)
                 or (kind == "ip" and bool(source["cidrs"]) and not source["public_suffixes"])
                 or (kind == "transport" and bool(ports) and not source["cidrs"] and not source["public_suffixes"]),
                 "source scope/kind mismatch")
    else:
        raise OverlayError("unsupported source type")


def load_manifest(root=ROOT):
    """Return entries in declared order after strict schema/graph/path validation."""
    data = _json(root, MANIFEST)
    _fields(data, {"version", "overlays"})
    _require(type(data["version"]) is int and data["version"] == 1, "unsupported overlay manifest version")
    entries = data["overlays"]
    _require(isinstance(entries, list) and bool(entries), "empty overlay manifest")
    by_name = {}
    paths = set()
    for entry in entries:
        _fields(entry, {"name", "kind", "clients", "reason", "placement", "before", "conflicts", "sources"})
        name = entry["name"]
        _require(isinstance(name, str) and NAME.fullmatch(name) and name not in by_name,
                 "invalid or duplicate overlay name")
        _require(isinstance(entry["kind"], str) and entry["kind"] in KINDS
                 and isinstance(entry["placement"], str) and entry["placement"] in PLACEMENTS,
                 "invalid overlay kind or placement")
        _require(set(_strings(entry["clients"])) <= CLIENTS, "unsupported intended client")
        _text(entry["reason"])
        for field in ("before", "conflicts"):
            _strings(entry[field], empty=True)
            _require(name not in entry[field], "self-referential ordering/conflict")
        _require(isinstance(entry["sources"], list) and bool(entry["sources"]), "empty overlay sources")
        seen_sources = set()
        for source in entry["sources"]:
            _validate_source(source, entry["kind"], root)
            key = (source["type"], source.get("path", source.get("name")))
            _require(key not in seen_sources, "duplicate composition source")
            seen_sources.add(key)
            if source["type"] == "file":
                paths.add(source["path"])
        by_name[name] = entry
    positions = {e["name"]: i for i, e in enumerate(entries)}
    for entry in entries:
        name = entry["name"]
        for target in entry["before"]:
            _require(target in by_name and positions[name] < positions[target],
                     "overlay order violates before constraint")
        for target in entry["conflicts"]:
            _require(target in by_name and name in by_name[target]["conflicts"],
                     "conflicts must be known and symmetric")
    visited, active = set(), set()

    def visit(name):
        _require(name in by_name, "unknown composition dependency")
        _require(name not in active, "overlay composition cycle")
        if name in visited:
            return
        active.add(name)
        for source in by_name[name]["sources"]:
            if source["type"] == "overlay":
                target = source["name"]
                visit(target)
                _require(by_name[target]["kind"] == by_name[name]["kind"], "mixed domain/IP composition")
        active.remove(name)
        visited.add(name)

    for name in by_name:
        visit(name)
    folder = _path(root, "overlays/sources")
    actual = set()
    for path in folder.rglob("*"):
        relative = path.relative_to(root).as_posix()
        _path(root, relative)
        if not path.is_dir():
            actual.add(relative)
    _require(actual == paths, "unreferenced or missing curated source file")
    return entries


def _campus_rules(root):
    data = _json(root, "config/campus-services.json")
    _fields(data, {"version", "scope", "families"})
    _require(type(data["version"]) is int and data["version"] == 1, "unsupported campus schema")
    _text(data["scope"])
    _require(isinstance(data["families"], list) and bool(data["families"]), "empty campus families")
    names, rules = set(), []
    for family in data["families"]:
        _fields(family, {"name", "evidence", "suffixes"})
        _text(family["name"])
        _require(family["name"] not in names, "duplicate campus family")
        names.add(family["name"])
        for evidence in _strings(family["evidence"]):
            _require(evidence.startswith("https://") or evidence == "lists/ChinaDomain.list",
                     "campus evidence must be a public reference")
        for suffix in _strings(family["suffixes"]):
            rules.append(parse_rule("DOMAIN-SUFFIX," + suffix, "domain"))
    return rules


def _file_rules(root, source, kind):
    rules = []
    for line in _read(root, source["path"]).splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Never propagate comments from input files into distribution files.
        rule = parse_rule(line.split(" #", 1)[0].strip(), kind,
                          add_no_resolve=source["type"] == "common")
        leaves = _leaves(rule)
        _require(not (len(leaves) == 1 and leaves[0][0] == "PROTOCOL"),
                 "unconstrained protocol rule forbidden")
        if source["type"] == "file":
            if kind == "ip" and source["ports"]:
                _require(len(leaves) == 2, "port-constrained IP source requires a conjunction")
            for parts in leaves:
                if parts[0] in DOMAIN_TYPES:
                    value = parts[1]
                    _require(any(value == scope or (not any(c in scope for c in "*?")
                                                   and value.endswith("." + scope))
                                 for scope in source["public_suffixes"]),
                             "domain outside reviewed public namespace")
                elif parts[0] in IP_TYPES:
                    _require(parts[1] in source["cidrs"], "CIDR outside reviewed source scope")
                elif parts[0] == "DEST-PORT":
                    _require(int(parts[1]) in source["ports"], "port outside reviewed source scope")
        rules.append(rule)
    _require(bool(rules), "empty policy-free source")
    _require(len(set(rules)) == len(rules), "duplicate source rule")
    return rules


def compose(root=ROOT):
    """Return (entries, rules_by_name, transitive_input_paths_by_name).

    Union is stable, exact deduplication in declared source order. No suffix/IP
    collapse can broaden a source or change the UK inline exception spelling.
    """
    root = Path(root)
    entries = load_manifest(root)
    by_name = {e["name"]: e for e in entries}
    rules, inputs = {}, {}

    def expand(name):
        if name in rules:
            return
        result, dependencies = [], {MANIFEST}
        for source in by_name[name]["sources"]:
            if source["type"] == "overlay":
                expand(source["name"])
                result.extend(rules[source["name"]])
                dependencies.update(inputs[source["name"]])
            else:
                dependencies.add(source["path"])
                result.extend(_campus_rules(root) if source["type"] == "campus-services"
                              else _file_rules(root, source, by_name[name]["kind"]))
        rules[name] = tuple(dict.fromkeys(result))
        inputs[name] = tuple(sorted(dependencies))

    for entry in entries:
        expand(entry["name"])
    return entries, rules, inputs


def provider_name(name):
    _require(isinstance(name, str) and NAME.fullmatch(name), "invalid overlay name")
    return "DeviceOverlay" + name


def ordered_selection(names, client, root=ROOT):
    """Select intended overlays in manifest order; never insert common rules.

    Consumers still honor each placement boundary and retain private guards.
    Composition dependencies do not automatically become separate routing calls.
    """
    names = _strings(list(names), empty=True)
    entries = load_manifest(root)
    _require(client in CLIENTS, "unsupported client")
    selected = [e for e in entries if e["name"] in names]
    _require(len(selected) == len(names), "unknown selected overlay")
    for entry in selected:
        _require(client in entry["clients"], "overlay not intended for client")
        _require(not set(entry["conflicts"]) & set(names), "conflicting overlay variants")
    return selected


def render_call(name, policy, *, mihomo=False, root=ROOT):
    """Render one caller-policy binding, not a complete device configuration."""
    _require(isinstance(policy, str) and bool(policy) and policy == policy.strip()
             and not any(c in policy for c in ",\r\n#()"), "invalid caller policy")
    entries = {e["name"]: e for e in load_manifest(root)}
    _require(name in entries, "unknown overlay")
    ref = provider_name(name) if mihomo else f"{CDN_BASE}/overlays/surge/{name}.list"
    suffix = ",no-resolve" if entries[name]["kind"] == "ip" else ""
    return f"RULE-SET,{ref},{policy}{suffix}"


def build(root=ROOT):
    """Pure build: {repository-relative output path: UTF-8 text}, no writes."""
    root = Path(root)
    initial_entries = load_manifest(root)
    input_paths = {MANIFEST} | {s["path"] for e in initial_entries for s in e["sources"] if "path" in s}
    snapshot = {path: _path(root, path).read_bytes() for path in sorted(input_paths)}
    entries, rules, dependencies = compose(root)
    artifacts, catalog = {}, []
    providers = ["# Generated by tools/device_overlays.py; optional policy-free providers only.",
                 "# Merge selected providers; bind policies and ordering in the private profile.",
                 "rule-providers:"]
    for entry in entries:
        name = entry["name"]
        paths = {client: f"overlays/{client}/{name}.list" for client in ("surge", "clash")}
        for client, path in paths.items():
            lines = ["# Generated by tools/device_overlays.py; do not edit.",
                     f"# {name}: optional {entry['kind']} overlay; no policy bindings.",
                     "# Composition: config/device-overlays.json. Integration: docs/DEVICE-OVERLAYS.md.", ""]
            lines.extend(to_mihomo(rule) if client == "clash" else rule for rule in rules[name])
            artifacts[path] = "\n".join(lines) + "\n"
        provider = provider_name(name)
        providers.extend([f"  {provider}:", "    type: http", "    behavior: classical", "    format: text",
                          f"    url: {CDN_BASE}/{paths['clash']}",
                          f"    path: ./rule-sets/surge-rules/device-overlays/v1/{name}.list", "    interval: 86400"])
        catalog.append({key: entry[key] for key in ("name", "kind", "clients", "reason", "placement", "before", "conflicts")} | {
            "inputs": list(dependencies[name]), "rule_count": len(rules[name]),
            "surge": {"path": paths["surge"], "url": f"{CDN_BASE}/{paths['surge']}",
                      "no_resolve": entry["kind"] == "ip"},
            "clash": {"path": paths["clash"], "url": f"{CDN_BASE}/{paths['clash']}", "provider": provider}})
    artifacts["overlays/clash/rule-providers.yaml"] = "\n".join(providers) + "\n"
    inputs = sorted(set().union(*map(set, dependencies.values())))
    _require(set(inputs) == set(snapshot)
             and all(_path(root, p).read_bytes() == snapshot[p] for p in inputs),
             "public sources changed during build; retry after the concurrent edit")
    artifacts["overlays/index.json"] = json.dumps({"version": 1, "inputs": {
        path: hashlib.sha256(snapshot[path]).hexdigest() for path in inputs},
        "overlays": catalog}, ensure_ascii=True, indent=2) + "\n"
    return artifacts


def drift(artifacts, root=ROOT):
    """Return changed/missing and unexpected generated paths without writing."""
    root = Path(root)
    changed = []
    for relative, text in artifacts.items():
        path = _path(root, relative)
        if not path.is_file() or path.read_bytes() != text.encode("utf-8"):
            changed.append(relative)
    actual = set()
    for path in _path(root, "overlays").rglob("*"):
        relative = path.relative_to(root).as_posix()
        _path(root, relative)
        if not path.is_dir():
            actual.add(relative)
    inputs = set(json.loads(artifacts["overlays/index.json"])["inputs"])
    return sorted(changed), sorted(actual - set(artifacts) - inputs)


def write_artifacts(artifacts, root=ROOT):
    """Replace changed files atomically, only after the entire build validates.

    Unexpected files are a blocker, not permission to delete concurrent work.
    """
    changed, stale = drift(artifacts, root)
    _require(not stale, "unexpected generated files; inspect them before rebuilding")
    for relative in changed:
        path = _path(root, relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix="." + path.name + ".", dir=path.parent)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(artifacts[relative].encode("utf-8"))
            os.chmod(temporary, 0o644)
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    return changed


def validate_native(artifacts):
    """Offline native checks with negative controls proving inline payload parsing.

    Mihomo -t validates provider declarations but does not load provider bodies.
    A second config expands the generated classical payloads into inline rules.
    No private profile, active instance, download, TUN or listener is needed.
    Diagnostics stay in a temporary directory if a check fails.
    """
    surge = shutil.which("surge-cli") or "/Applications/Surge.app/Contents/Applications/surge-cli"
    mihomo = shutil.which("mihomo")
    _require(Path(surge).is_file() and bool(mihomo), "native checks require surge-cli and mihomo")
    with tempfile.TemporaryDirectory(prefix="device-overlay-check-") as temp:
        folder = Path(temp)
        names = [Path(p).stem for p in artifacts if p.startswith("overlays/surge/")]
        profile = ["[General]", "loglevel = warning", "[Rule]"]
        profile.extend(f"RULE-SET,{name},DIRECT" for name in names)
        profile.append("FINAL,DIRECT")
        for name in names:
            profile.extend([f"[Ruleset {name}]", artifacts[f"overlays/surge/{name}.list"].rstrip()])
        surge_path = folder / "Surge.conf"
        surge_text = "\n".join(profile) + "\n"
        surge_path.write_text(surge_text, encoding="utf-8")
        providers = {}
        for name in names:
            relative = f"providers/{name}.list"
            path = folder / relative
            path.parent.mkdir(exist_ok=True)
            path.write_text(artifacts[f"overlays/clash/{name}.list"], encoding="utf-8")
            providers[provider_name(name)] = {"type": "file", "behavior": "classical", "format": "text", "path": "./" + relative}
        # JSON is a YAML subset; no PyYAML dependency and no active runtime.
        mihomo_path = folder / "Mihomo.yaml"
        mihomo_path.write_text(json.dumps({"mode": "rule", "log-level": "error", "ipv6": True,
            "tun": {"enable": False}, "dns": {"enable": False}, "rule-providers": providers,
            "rules": [f"RULE-SET,{provider_name(name)},DIRECT" for name in names] + ["MATCH,DIRECT"]}), encoding="utf-8")

        def run(command, expected_success):
            try:
                result = subprocess.run(command, capture_output=True, text=True, timeout=60)
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise OverlayError("native syntax check could not complete") from exc
            if (result.returncode == 0) != expected_success:
                log_dir = Path(tempfile.mkdtemp(prefix="device-overlay-native-error-"))
                log = log_dir / "native.log"
                log.write_text(result.stdout + result.stderr, encoding="utf-8")
                log.chmod(0o600)
                raise OverlayError("native syntax/negative-control failure; log: " + str(log))

        surge_command = [surge, "--check", str(surge_path)]
        mihomo_command = [mihomo, "-t", "-d", str(folder), "-f", str(mihomo_path)]
        run(surge_command, True)
        run(mihomo_command, True)
        inline_rules = []
        for name in names:
            for line in artifacts[f"overlays/clash/{name}.list"].splitlines():
                if line and not line.startswith("#"):
                    parts = split_fields(line)
                    inline_rules.append(",".join(parts[:2] + ["DIRECT"] + parts[2:]))
        inline_config = {"mode": "rule", "log-level": "error", "ipv6": True,
                         "tun": {"enable": False}, "dns": {"enable": False},
                         "rules": inline_rules + ["MATCH,DIRECT"]}
        mihomo_path.write_text(json.dumps(inline_config), encoding="utf-8")
        run(mihomo_command, True)
        surge_path.write_text(surge_text + "UNSUPPORTED-OVERLAY-RULE,example.com\n", encoding="utf-8")
        run(surge_command, False)
        inline_config["rules"] = ["UNSUPPORTED-OVERLAY-RULE,example.com,DIRECT", "MATCH,DIRECT"]
        mihomo_path.write_text(json.dumps(inline_config), encoding="utf-8")
        run(mihomo_command, False)
    return len(names)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="compare generated bytes without writing (exit 1 on drift)")
    parser.add_argument("--native", action="store_true", help="also require offline Surge and Mihomo native syntax checks")
    args = parser.parse_args(argv)
    try:
        artifacts = build(ROOT)
        if args.native:
            count = validate_native(artifacts)
            print(f"Native syntax and negative controls passed: {count} overlays, Surge + Mihomo")
        changed, stale = drift(artifacts, ROOT)
        if args.check:
            if changed or stale:
                print("Overlay drift (no files written):")
                for path in changed + stale:
                    print("  " + path)
                return 1
            print(f"Device overlays current: {len(artifacts)} artifacts")
        else:
            written = write_artifacts(artifacts, ROOT)
            print(f"Device overlays built: {len(artifacts)} artifacts, {len(written)} changed")
        return 0
    except (OverlayError, OSError) as exc:
        print("Device overlay validation failed: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
