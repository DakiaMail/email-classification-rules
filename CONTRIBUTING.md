# Contributing

Propose a focused change to `rules/core.json`, describe the false match or
missing case, and add synthetic examples in `tests/fixtures.json`.

Every rule needs a positive example that lists it in `matches` and a negative
example that lists it in `not_matches`. Assert all three outputs, including
unknown values. Include conflicting cases where relevant: a receipt with a
discount footer, a newsletter discussing security, a security code from a
delivery platform, or a sender-domain lookalike.

Use combined evidence for decisions. No-reply addresses, unsubscribe headers,
reply headers, display names and delivery-platform domains cannot determine a
category alone. A company can send receipts, account alerts and marketing from
the same domain. Keep brand rules narrow and do not treat domain membership as
proof of authentication.

Keep Primary for personal correspondence and actionable individual messages.
Routine confirmations belong in Transactions. Editorial newsletters, social
and policy notices belong in Updates. Commercial offers belong in Promotions.
Newsletter and time-sensitive flags are independent. An offer ending tonight
does not make it an actionable security or account deadline.

Keep the pattern subset portable and follow [docs/format.md](docs/format.md).
Add provenance for borrowed material, including a fixed revision and permission
to redistribute it under MIT. Contributions must be material you have the right
to contribute under this repository's MIT license. Preserve existing notices.

Never submit real messages, screenshots of mail, personal sender overrides,
recipient addresses, unsubscribe tokens, account identifiers, private labels,
learned profiles or private evaluation results. Write examples from scratch
using reserved example domains, except when a public service domain is needed
to test a domain rule. Invent subjects, bodies and local parts. An `.eml` export
is not an acceptable test fixture.

Run:

```sh
python3 reference/matcher.py --check
python3 -m unittest discover -s tests -v
```

For rule changes, bump the ruleset version and the local source revision record
together. Describe the expected behavior change in the pull request. Maintainers
review matches, exceptions, priority interactions, provenance and privacy before
publishing a versioned release. Synthetic test success does not establish
accuracy on real mail.
