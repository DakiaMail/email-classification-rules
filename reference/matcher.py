"""Reference semantics for the public JSON rules. Not a MIME parser or mail client."""

import argparse
import json
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
CATEGORIES = {"primary", "transactions", "updates", "promotions"}
OUTPUTS = {"category", "newsletter", "time_sensitive"}
HEADER_NAMES = {
    "list-id", "list-unsubscribe", "list-unsubscribe-post", "precedence",
    "auto-submitted", "in-reply-to", "references", "content-type",
}
STRING_FIELDS = {"subject", "text", "sender_address", "sender_domain", "sender_local"}
STRING_FIELDS |= {f"headers.{name}" for name in HEADER_NAMES}
BOOL_FIELDS = {"sender_authenticated", "verified_correspondent", "has_calendar_part"}
FIELDS = STRING_FIELDS | BOOL_FIELDS | {"gmail_categories"}
INPUT_FIELDS = {"subject", "text", "sender_address", "headers", "gmail_categories"} | BOOL_FIELDS
GMAIL_CATEGORIES = {"primary", "updates", "promotions", "social", "forums"}
MAX_MESSAGE_BYTES = 262_144


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def read_json(text):
    return json.loads(text, object_pairs_hook=_unique_object)


def _validate_condition(node, depth=0):
    _require(depth <= 8 and isinstance(node, dict), "Invalid condition nesting")
    if set(node) in ({"all"}, {"any"}):
        children = next(iter(node.values()))
        _require(isinstance(children, list) and 1 <= len(children) <= 16, "Invalid condition list")
        for child in children:
            _validate_condition(child, depth + 1)
        return
    if set(node) == {"not"}:
        _validate_condition(node["not"], depth + 1)
        return
    _require(set(node) <= {"field", "op", "value"} and {"field", "op"} <= set(node), "Invalid predicate")
    field, op = node["field"], node["op"]
    _require(isinstance(field, str) and field in FIELDS, "Unknown condition field")
    if op == "present":
        _require(field in STRING_FIELDS and set(node) == {"field", "op"}, "Invalid present predicate")
    elif op == "equals":
        value = node.get("value")
        _require((field in BOOL_FIELDS and type(value) is bool) or
                 (field in STRING_FIELDS and isinstance(value, str)), "Invalid equality predicate")
    elif op == "contains":
        _require(field == "gmail_categories" and isinstance(node.get("value"), str) and
                 node["value"] in GMAIL_CATEGORIES, "Invalid category predicate")
    elif op == "domain_in":
        values = node.get("value")
        _require(field == "sender_domain" and isinstance(values, list) and 1 <= len(values) <= 64,
                 "Invalid domain predicate")
        for value in values:
            _require(isinstance(value, str) and re.fullmatch(r"[a-z0-9]+(?:[.-][a-z0-9]+)*\.[a-z]{2,}", value),
                     "Invalid domain")
    elif op == "regex":
        pattern = node.get("value")
        _require(field in STRING_FIELDS and isinstance(pattern, str) and 0 < len(pattern) <= 512,
                 "Invalid regex predicate")
        # Keep reviewed patterns portable; never evaluate executable rule expressions.
        _require(not re.search(r"[+*]|\\[1-9]|\(\?(?!:)|\)[?{]", pattern), "Unsupported regex construct")
        for repeat in re.findall(r"\{([^{}]*)\}", pattern):
            _require(re.fullmatch(r"\d{1,2}(?:,\d{1,2})?", repeat) is not None, "Unbounded repeat")
            limits = [int(part) for part in repeat.split(",")]
            _require(limits[0] <= limits[-1] <= 32, "Invalid repeat bounds")
        try:
            re.compile(pattern, re.IGNORECASE | re.ASCII)
        except re.error as error:
            raise ValueError("Invalid regex") from error
    else:
        raise ValueError("Unknown predicate operator")


def validate_rules(document):
    _require(isinstance(document, dict) and set(document) == {"format_version", "version", "license", "license_text", "sources", "rules"},
             "Invalid ruleset fields")
    _require(type(document["format_version"]) is int and document["format_version"] == 1, "Unsupported format version")
    _require(isinstance(document["version"], str) and re.fullmatch(r"\d+\.\d+\.\d+", document["version"]), "Invalid version")
    _require(document["license"] == "MIT", "Missing MIT license declaration")
    _require(isinstance(document["license_text"], str) and document["license_text"].startswith("MIT License\n") and
             "Copyright (c) 2026 Kiera Bridgeman (kbridgie01)" in document["license_text"], "Missing license notice")
    sources = document["sources"]
    _require(isinstance(sources, dict) and sources, "Missing sources")
    for source_id, source in sources.items():
        _require(isinstance(source_id, str) and isinstance(source, dict) and
                 set(source) == {"url", "revision", "license", "files"}, "Invalid source record")
        _require(isinstance(source["url"], str) and source["url"].startswith("https://"), "Invalid source URL")
        _require(isinstance(source["revision"], str) and source["revision"], "Missing source revision")
        _require(source["license"] == "MIT" and isinstance(source["files"], list) and source["files"] and
                 all(isinstance(path, str) and path for path in source["files"]), "Invalid source license or files")
    rules = document["rules"]
    _require(isinstance(rules, list) and 1 <= len(rules) <= 128, "Invalid rule count")
    ids = set()
    for rule in rules:
        _require(isinstance(rule, dict) and set(rule) == {"id", "description", "mode", "priority", "when", "set", "sources"},
                 "Invalid rule fields")
        rule_id = rule["id"]
        _require(isinstance(rule_id, str) and re.fullmatch(r"[a-z][a-z0-9.-]{0,79}", rule_id) and rule_id not in ids,
                 "Invalid or duplicate rule ID")
        ids.add(rule_id)
        _require(isinstance(rule["description"], str) and 0 < len(rule["description"]) <= 300, "Missing rule description")
        _require(rule["mode"] in ("decision", "hint"), "Invalid rule mode")
        _require(type(rule["priority"]) is int and 0 <= rule["priority"] <= 100, "Invalid priority")
        effects = rule["set"]
        _require(isinstance(effects, dict) and effects and set(effects) <= OUTPUTS, "Invalid rule output")
        for key, value in effects.items():
            _require((key == "category" and isinstance(value, str) and value in CATEGORIES) or
                     (key != "category" and type(value) is bool), "Invalid output value")
        _require(isinstance(rule["sources"], list) and rule["sources"] and
                 all(isinstance(source, str) and source in sources for source in rule["sources"]), "Unknown source")
        _validate_condition(rule["when"])
    return document


def load_rules(path=ROOT / "rules/core.json"):
    data = Path(path).read_bytes()
    _require(len(data) <= 262_144, "Ruleset exceeds 256 KiB")
    return validate_rules(read_json(data.decode("utf-8")))


def normalize_message(message):
    _require(isinstance(message, dict) and set(message) <= INPUT_FIELDS, "Unknown message field")
    result = {}
    for field, limit in (("subject", 4096), ("text", 32768), ("sender_address", 320)):
        value = message.get(field, "")
        _require(isinstance(value, str), f"Expected a string for {field}")
        # Reject oversized structured addresses rather than accepting a truncated identity.
        if field == "sender_address":
            _require(len(value) <= limit, "Sender address exceeds 320 characters")
        result[field] = value[:limit]
    address = result["sender_address"].strip().lower()
    _require(not address or (address.count("@") == 1 and not re.search(r"[\s<>]", address)),
             "sender_address must be a parsed address, without a display name")
    if address:
        local, domain = address.split("@")
        _require(bool(local) and bool(domain), "Invalid sender address")
        try:
            domain = domain.removesuffix(".").encode("idna").decode("ascii")
        except UnicodeError as error:
            raise ValueError("Invalid sender domain") from error
        _require(len(domain) <= 253 and all(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", part)
                                          for part in domain.split(".")), "Invalid sender domain")
    else:
        local, domain = "", ""
    result.update(sender_address=f"{local}@{domain}" if address else "", sender_domain=domain, sender_local=local)
    for field in BOOL_FIELDS:
        value = message.get(field, False)
        _require(type(value) is bool, f"Expected a boolean for {field}")
        result[field] = value
    categories = message.get("gmail_categories", [])
    _require(isinstance(categories, list) and all(isinstance(value, str) and value in GMAIL_CATEGORIES for value in categories),
             "Invalid Gmail categories")
    result["gmail_categories"] = sorted(set(categories))
    headers = message.get("headers", {})
    _require(isinstance(headers, dict) and len(headers) <= 128, "Invalid headers")
    seen = set()
    for name, value in headers.items():
        _require(isinstance(name, str) and isinstance(value, str), "Header names and values must be strings")
        name = name.strip().lower()
        _require(name not in seen, "Duplicate header name after normalization")
        seen.add(name)
        if name in HEADER_NAMES:
            result[f"headers.{name}"] = value[:2048].strip()
    for name in HEADER_NAMES:
        result.setdefault(f"headers.{name}", "")
    return result


def matches(node, fields):
    if "all" in node:
        return all(matches(child, fields) for child in node["all"])
    if "any" in node:
        return any(matches(child, fields) for child in node["any"])
    if "not" in node:
        return not matches(node["not"], fields)
    actual, op = fields[node["field"]], node["op"]
    value = node.get("value")
    if op == "present":
        return bool(actual)
    if op == "equals":
        return actual == value
    if op == "contains":
        return value in actual
    if op == "domain_in":
        return any(actual == domain or actual.endswith("." + domain) for domain in value)
    if op == "regex":
        return re.search(value, actual, re.IGNORECASE | re.ASCII) is not None
    raise ValueError("Unknown operator")


def classify(message, document):
    fields = normalize_message(message)
    matched = sorted((rule for rule in document["rules"] if matches(rule["when"], fields)), key=lambda rule: rule["id"])
    result = {key: None for key in sorted(OUTPUTS)}
    result.update(matched_rules=[rule["id"] for rule in matched], hints=[], conflicts={}, evidence={})
    for rule in matched:
        if rule["mode"] == "hint":
            result["hints"].append({"rule": rule["id"], "suggests": rule["set"]})
    for key in sorted(OUTPUTS):
        candidates = [rule for rule in matched if rule["mode"] == "decision" and key in rule["set"]]
        if not candidates:
            continue
        priority = max(rule["priority"] for rule in candidates)
        winners = [rule for rule in candidates if rule["priority"] == priority]
        evidence = [rule["id"] for rule in winners]
        values = {rule["set"][key] for rule in winners}
        result["evidence"][key] = evidence
        if len(values) == 1:
            result[key] = next(iter(values))
        else:
            result["conflicts"][key] = evidence
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rules", type=Path, default=ROOT / "rules/core.json")
    parser.add_argument("--check", action="store_true", help="validate rules and exit")
    args = parser.parse_args()
    try:
        rules = load_rules(args.rules)
        if args.check:
            print(f"Validated {len(rules['rules'])} rules ({rules['version']}).")
            return
        raw = sys.stdin.buffer.read(MAX_MESSAGE_BYTES + 1)
        _require(len(raw) <= MAX_MESSAGE_BYTES, "Message exceeds 256 KiB")
        result = classify(read_json(raw.decode("utf-8")), rules)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    except (ValueError, OSError) as error:
        # Input may contain private mail; errors must not echo it.
        print(f"Invalid input or rules: {type(error).__name__}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
