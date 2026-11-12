import copy
import json
import subprocess
import sys
import unittest

from reference.matcher import (
    BOOL_FIELDS, ROOT, classify, load_rules, normalize_message, read_json, validate_rules,
)


class RulesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules = load_rules()
        cls.fixtures = read_json((ROOT / "tests/fixtures.json").read_text())

    def test_synthetic_conformance_cases(self):
        names = set()
        for fixture in self.fixtures:
            with self.subTest(fixture["name"]):
                self.assertNotIn(fixture["name"], names)
                names.add(fixture["name"])
                result = classify(fixture["message"], self.rules)
                self.assertEqual(set(fixture["expected"]), {"category", "newsletter", "time_sensitive"})
                for key, expected in fixture["expected"].items():
                    self.assertEqual(result[key], expected, key)
                for rule in fixture["matches"]:
                    self.assertIn(rule, result["matched_rules"])
                for rule in fixture["not_matches"]:
                    self.assertNotIn(rule, result["matched_rules"])

    def test_every_rule_has_positive_and_negative_examples(self):
        ids = {rule["id"] for rule in self.rules["rules"]}
        positives = {rule for fixture in self.fixtures for rule in fixture["matches"]}
        negatives = {rule for fixture in self.fixtures for rule in fixture["not_matches"]}
        self.assertEqual(positives, ids)
        self.assertEqual(negatives, ids)

    def test_no_rule_order_dependency(self):
        reordered = copy.deepcopy(self.rules)
        reordered["rules"].reverse()
        for fixture in self.fixtures:
            with self.subTest(fixture["name"]):
                self.assertEqual(classify(fixture["message"], self.rules), classify(fixture["message"], reordered))

    def test_standalone_rules_preserve_license_and_pinned_provenance(self):
        self.assertEqual(self.rules["license_text"], (ROOT / "LICENSE").read_text())
        notice = "Copyright (c) 2026 Kiera Bridgeman (kbridgie01)"
        self.assertIn(notice, (ROOT / "third_party/gmail-inbox-cleaner.LICENSE").read_text())
        upstream = self.rules["sources"]["gmail-inbox-cleaner"]
        self.assertEqual(upstream["revision"], "37ef90b3851416551f2a92130608860ee7feade6")
        self.assertEqual(self.rules["sources"]["dakia"]["revision"], "v" + self.rules["version"])

    def test_hint_does_not_set_category_or_flags(self):
        result = classify({"sender_address": "noreply@example.com"}, self.rules)
        self.assertIsNone(result["category"])
        self.assertIsNone(result["newsletter"])
        self.assertIsNone(result["time_sensitive"])
        self.assertEqual(result["hints"], [{"rule": "hints.no-reply", "suggests": {"category": "updates"}}])

    def test_conflicting_categories_do_not_silently_pick_a_winner(self):
        result = classify({"gmail_categories": ["primary", "promotions"]}, self.rules)
        self.assertIsNone(result["category"])
        self.assertEqual(result["conflicts"], {"category": ["gmail.primary", "gmail.promotions"]})
        self.assertEqual(result["evidence"]["category"], ["gmail.primary", "gmail.promotions"])

    def test_conflict_resolution_is_per_output(self):
        document = copy.deepcopy(self.rules)
        decision = next(rule for rule in document["rules"] if rule["id"] == "gmail.primary")
        decision["set"].update(newsletter=False, time_sensitive=True)
        other = next(rule for rule in document["rules"] if rule["id"] == "gmail.promotions")
        other["set"]["newsletter"] = True
        validate_rules(document)
        result = classify({"gmail_categories": ["primary", "promotions"]}, document)
        self.assertIsNone(result["category"])
        self.assertIsNone(result["newsletter"])
        self.assertTrue(result["time_sensitive"])
        self.assertEqual(set(result["conflicts"]), {"category", "newsletter"})

    def test_higher_priority_decision_resolves_lower_priority_conflicts(self):
        result = classify({"gmail_categories": ["primary", "promotions"], "subject": "Your receipt",
                           "text": "Total paid: EUR 10."}, self.rules)
        self.assertEqual(result["category"], "transactions")
        self.assertEqual(result["conflicts"], {})
        self.assertEqual(result["evidence"]["category"], ["transactions.receipt"])

    def test_case_normalization_and_domain_boundaries(self):
        message = {"sender_address": "Writer@Letters.Substack.COM.", "sender_authenticated": True,
                   "headers": {"LIST-UNSUBSCRIBE": " <https://example.com/unsubscribe> "}}
        self.assertEqual(classify(message, self.rules)["category"], "updates")
        for domain in ["notsubstack.com", "substack.com.example.com", "substack-com.example.com"]:
            message["sender_address"] = "writer@" + domain
            self.assertNotIn("updates.publisher", classify(message, self.rules)["matched_rules"])

    def test_idna_domain_normalization(self):
        self.assertEqual(normalize_message({"sender_address": "reader@bücher.example"})["sender_domain"],
                         "xn--bcher-kva.example")

    def test_english_patterns_have_ascii_word_boundaries(self):
        message = {"subject": "Newsletter：文章", "text": "Unsubscribe here."}
        self.assertEqual(classify(message, self.rules)["newsletter"], True)
        message["subject"] = "newsletterish"
        self.assertIsNone(classify(message, self.rules)["category"])

    def test_bounded_preprocessing(self):
        fields = normalize_message({"subject": "x" * 10000, "text": "界" * 100000,
                                    "headers": {"List-Id": "x" * 10000}})
        self.assertEqual(len(fields["subject"]), 4096)
        self.assertEqual(len(fields["text"]), 32768)
        self.assertEqual(len(fields["headers.list-id"]), 2048)
        result = classify({"subject": "x" * 4096 + " Your order confirmation"}, self.rules)
        self.assertIsNone(result["category"])

    def test_header_values_do_not_become_other_metadata(self):
        message = {"headers": {"X-Fake-Gmail-Category": "promotions", "List-Id": "Auto-Submitted: auto-generated"}}
        result = classify(message, self.rules)
        self.assertEqual(result["matched_rules"], ["hints.bulk"])
        self.assertIsNone(result["category"])

    def test_duplicate_json_keys_are_rejected(self):
        for raw in ['{"subject":"a","subject":"b"}', '{"headers":{"List-Id":"a","List-Id":"b"}}']:
            with self.subTest(raw), self.assertRaises(ValueError):
                read_json(raw)

    def test_invalid_messages_are_rejected(self):
        invalid = [[], {"body": "wrong field"}, {"subject": 1}, {"text": None}, {"headers": []},
                   {"headers": {"List-Id": 123}}, {"headers": {"List-Id": "a", "list-id": "b"}},
                   {"headers": {str(i): "x" for i in range(129)}}, {"gmail_categories": "promotions"},
                   {"gmail_categories": ["transactions"]}, {"gmail_categories": [{}]},
                   {"sender_address": "Brand <sender@example.com>"}, {"sender_address": "x" * 321},
                   {"sender_address": "bad@@example.com"}, {"sender_address": "@example.com"},
                   {"sender_address": "bad@example..com"}, {"sender_address": "bad@-example.com"}]
        invalid.extend({field: "true"} for field in BOOL_FIELDS)
        for message in invalid:
            with self.subTest(message=message), self.assertRaises(ValueError):
                classify(message, self.rules)

    def test_invalid_rule_outputs_and_provenance_are_rejected(self):
        patches = [
            {"set": {"category": "spam"}}, {"set": {"newsletter": 1}}, {"set": {}},
            {"set": {"time_sensitive": "true"}}, {"set": {"execute": "a command"}},
            {"sources": ["missing"]}, {"sources": []}, {"mode": "code"}, {"priority": True},
            {"priority": 101}, {"description": ""}, {"id": "INVALID ID"}, {"surprise": True},
        ]
        for patch in patches:
            document = copy.deepcopy(self.rules)
            document["rules"][0].update(patch)
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                validate_rules(document)
        document = copy.deepcopy(self.rules)
        document["rules"].append(document["rules"][0])
        with self.assertRaises(ValueError):
            validate_rules(document)

    def test_invalid_predicates_are_rejected(self):
        nodes = [
            {"all": []}, {"any": []}, {"field": "body", "op": "present"},
            {"field": "subject", "op": "execute", "value": "anything"},
            {"field": "subject", "op": "regex", "value": "(a+)+"},
            {"field": "subject", "op": "regex", "value": "(?=secret)"},
            {"field": "subject", "op": "regex", "value": "a{1,}"},
            {"field": "subject", "op": "regex", "value": "a{1,99}"},
            {"field": "subject", "op": "regex", "value": "["},
            {"field": "subject", "op": "present", "value": True},
            {"field": "sender_authenticated", "op": "equals", "value": "true"},
            {"field": "gmail_categories", "op": "contains", "value": []},
            {"field": "sender_domain", "op": "domain_in", "value": [".example.com"]},
            {"field": "sender_domain", "op": "domain_in", "value": []},
        ]
        nested = {"field": "subject", "op": "present"}
        for _ in range(10):
            nested = {"not": nested}
        nodes.append(nested)
        for node in nodes:
            document = copy.deepcopy(self.rules)
            document["rules"][0]["when"] = node
            with self.subTest(node=node), self.assertRaises(ValueError):
                validate_rules(document)

    def test_invalid_documents_are_rejected(self):
        for patch in [{"format_version": 2}, {"format_version": True}, {"version": "latest"},
                      {"license": "unknown"}, {"sources": {}}, {"rules": []}, {"extra": True}]:
            document = copy.deepcopy(self.rules)
            document.update(patch)
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                validate_rules(document)

    def test_cli_emits_a_single_json_result(self):
        message = {"subject": "Get up to 25% OFF", "text": "Shop now. Unsubscribe here."}
        process = subprocess.run([sys.executable, "reference/matcher.py"], input=json.dumps(message),
                                 text=True, capture_output=True, cwd=ROOT)
        self.assertEqual(process.returncode, 0, process.stderr)
        result = json.loads(process.stdout)
        self.assertEqual((result["category"], result["newsletter"], result["time_sensitive"]),
                         ("promotions", True, False))
        self.assertEqual(process.stderr, "")

    def test_cli_rejects_oversized_invalid_and_private_inputs_without_echoing(self):
        for payload in [b"x" * 262145, b'{"subject":', b'\xff', b'{"private-mail-marker":"private-content-marker"}',
                        b'{"subject":"private-content-marker","subject":"duplicate"}']:
            with self.subTest(size=len(payload)):
                process = subprocess.run([sys.executable, "reference/matcher.py"], input=payload,
                                         capture_output=True, cwd=ROOT)
                self.assertEqual(process.returncode, 2)
                self.assertEqual(process.stdout, b"")
                self.assertNotIn(b"private-content-marker", process.stderr)
                self.assertNotIn(b"private-mail-marker", process.stderr)

    def test_cli_check(self):
        process = subprocess.run([sys.executable, "reference/matcher.py", "--check"], text=True,
                                 capture_output=True, cwd=ROOT)
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertIn("Validated", process.stdout)


if __name__ == "__main__":
    unittest.main()
