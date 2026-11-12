# Email classification rules

Public, client-independent rules for sorting email into Primary, Transactions,
Updates and Promotions. Newsletter and time-sensitive are separate flags.

The rules are JSON data. They contain no mailbox actions, scripts, account
credentials or private messages. A dependency-free Python matcher defines and
tests the format; clients can implement the same semantics in any language.

This is a conservative starting collection, not a measured replacement for a
classifier. Uncertain messages remain unresolved, and weak signals are returned
as hints.

## Categories

| Value | Meaning |
| --- | --- |
| `primary` | Personal correspondence or a message requiring timely individual action, including authentication codes, actionable security alerts and failed payments. |
| `transactions` | Routine receipts, completed orders, invoices, shipping and booking confirmations. |
| `updates` | Newsletters, social notifications, calendar messages and service or policy updates. |
| `promotions` | Deals, discounts, offers and sales pitches. |

`newsletter` identifies subscription or digest mail, including promotional
newsletters. `time_sensitive` identifies actionable urgency, rather than a sale
ending soon. A flag can be `true`, `false`, or `null` when the rules do not know.
A category can also be `null`; it must not silently become Primary.

## Try it

Python 3.11 or newer is sufficient. No installation or account access is needed.

```sh
python3 reference/matcher.py --check
python3 -m unittest discover -s tests -v
python3 reference/matcher.py <<'JSON'
{
  "subject": "Get up to 25% OFF",
  "text": "Shop now. Unsubscribe here.",
  "headers": {"List-Unsubscribe": "<https://example.com/unsubscribe>"}
}
JSON
```

The result has `category: "promotions"`, `newsletter: true` and
`time_sensitive: false`, plus matched rule IDs and evidence. The matcher reads
one decoded JSON message from standard input and writes one JSON result. It
does not connect to a mailbox, follow links, write messages or learn from them.

## Use the data

Start with [rules/core.json](rules/core.json) and the normative
[format and matching contract](docs/format.md). Run the synthetic examples in
[tests/fixtures.json](tests/fixtures.json) against any client implementation.

Rules are resolved by priority separately for category and each flag. Equally
strong conflicting decisions leave that output unresolved. Hints never assign
a category or flag. Optional Gmail categories provide low-priority fallbacks.
Neither a no-reply address, an unsubscribe header, nor a reply header decides a
category on its own.

Clients should apply an explicit message correction before a personal sender
override, and both before community rules. Personal preferences and
correspondence history stay local. This repository implements no Dakia
integration or personalization store.

Pin a reviewed release or commit. Rules are untrusted content until reviewed;
the reference matcher is for this repository's reviewed patterns, not a sandbox
for arbitrary downloaded regex feeds. It is not a phishing or spam detector.

## Coverage and limits

The initial collection focuses on English phrases and a small set of public
service domains. Headers and provider categories can help with other languages,
but multilingual accuracy has not been evaluated. Authentication, MIME parsing
and the trustworthiness of provider metadata are responsibilities of the client.

Tests cover positive and negative examples for every rule, conflicting evidence,
domain lookalikes, metadata separation, bounded input, and malformed data. All
fixtures are synthetic. They establish format conformance, not real-mail
precision, recall, latency or memory use.

See [CONTRIBUTING.md](CONTRIBUTING.md) to propose a rule or report a false match.
Never attach private mail to an issue or pull request.

## License and provenance

MIT. Selected patterns were adapted from Kiera Bridgeman's
[gmail-inbox-cleaner](https://github.com/kbridgie01/gmail-inbox-cleaner) at a fixed
revision. See [ATTRIBUTION.md](ATTRIBUTION.md), [LICENSE](LICENSE), and the
[original license](third_party/gmail-inbox-cleaner.LICENSE).

The JSON also embeds the complete license notice so a standalone copy can
retain attribution. Preserve it when redistributing the rules.
