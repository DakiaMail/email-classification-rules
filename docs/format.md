# Format version 1

This document and the synthetic fixtures define the matching contract. JSON
object order and rule order have no effect. `reference/matcher.py` is the
executable reference and validator. No application integration is required.

## Ruleset

`rules/core.json` has exactly these keys:

- `format_version`: integer `1`.
- `version`: a semantic version string, currently `0.1.0`.
- `license`: `MIT`.
- `license_text`: the full MIT notice, including upstream and contributor copyright notices. Preserve this field when distributing the JSON on its own.
- `sources`: source IDs mapped to HTTPS URL, pinned revision, license and source files.
- `rules`: between 1 and 128 rules.

Each rule has `id`, `description`, `mode`, `priority`, `when`, `set` and `sources`.
IDs are unique lowercase ASCII identifiers. `mode` is `decision` or `hint`.
`priority` is an integer from 0 to 100. `sources` references the ruleset's source
records. `set` contains one or more of:

```json
{"category": "promotions", "newsletter": true, "time_sensitive": false}
```

Categories are `primary`, `transactions`, `updates`, or `promotions`. Flags in
rules are booleans. Omit an output if the rule has no opinion; do not set it to
`null`. Unknown outputs in the final result are `null`.

## Decoded message input

All input keys are optional. Unknown top-level keys are rejected.

| Key | Type and meaning |
| --- | --- |
| `subject` | String, MIME-decoded subject. |
| `text` | String, decoded visible body text. Do not supply raw HTML, scripts, hidden markup or transport headers here. |
| `sender_address` | Parsed From mailbox address, without a display name. |
| `headers` | Object of unfolded header names and string values from the MIME parser. |
| `gmail_categories` | Array containing normalized provider categories: `primary`, `updates`, `social`, `forums`, `promotions`. |
| `sender_authenticated` | Boolean, default false. Set only when the client verifies authentication aligned with the parsed From domain. |
| `verified_correspondent` | Boolean, default false. Client-owned evidence of previous personal correspondence, not the existence of a contact or a claim in the message. |
| `has_calendar_part` | Boolean, default false. A MIME parser found a calendar part. |

Map Gmail `CATEGORY_PERSONAL` to `primary`, `CATEGORY_PROMOTIONS` to `promotions`,
`CATEGORY_UPDATES` to `updates`, `CATEGORY_SOCIAL` to `social` and
`CATEGORY_FORUMS` to `forums`. Read these from provider state, never from a
sender-written `X-` header, body text or an arbitrary user label. Gmail labels
are optional evidence, not human-reviewed ground truth. There is no invented
Gmail Transactions category.

Verified correspondence decisions also require a parsed sender address.
Client-owned booleans must not be inferred from sender-written authentication
claims. Interpret trusted authentication results at the mail provider or
receiving server. The reference matcher accepts the booleans; it cannot verify
them itself.

For a raw message, decode MIME first and keep the parsed subject, visible text,
address and headers separate. The matcher does not extract metadata by scanning
the body. Quoted material and promotional footers can still create ambiguous
content signals; clients should test their text extraction against the fixtures.

## Normalization and bounds

- Standard input is UTF-8 JSON, at most 262,144 bytes. Duplicate JSON keys are rejected.
- Subject and text are kept as Unicode and truncated to 4,096 and 32,768 Unicode code points respectively, before matching.
- Sender addresses over 320 code points, display-name wrappers, whitespace inside addresses, and malformed domains are rejected. The whole address is lowercased, the domain is IDNA-encoded, and one trailing root dot is removed. Clients needing full RFC mailbox parsing must do it before this step.
- `sender_domain` and `sender_local` are derived from the address, not accepted as input keys.
- At most 128 header entries are accepted. Header names are trimmed and lowercased. Duplicate names after normalization are rejected. For repeated relevant headers, adapters must supply one unfolded value with a documented deterministic joining policy.
- Only `List-Id`, `List-Unsubscribe`, `List-Unsubscribe-Post`, `Precedence`, `Auto-Submitted`, `In-Reply-To`, `References` and `Content-Type` are retained. Values are truncated to 2,048 code points and trimmed. Other headers are ignored.
- Missing strings and relevant headers become empty strings; missing booleans become false; missing category lists become empty arrays. Gmail category arrays are deduplicated.

Do not fetch message URLs to classify. These limits describe conformance, not a
measured runtime budget. Adapters must enforce their own limits while decoding.

## Conditions

`when` is a predicate, `{"all": [conditions]}`, `{"any": [conditions]}`, or
`{"not": condition}`. `all` and `any` require 1 to 16 children. Nesting is
limited to eight levels. A predicate has `field`, `op`, and, except for
`present`, `value`.

| Operator | Meaning |
| --- | --- |
| `present` | A string field is nonempty. No `value` key. |
| `equals` | Exact string or boolean equality; no implicit type conversions. |
| `contains` | Exact membership in `gmail_categories`, not substring matching. |
| `domain_in` | `sender_domain` equals a listed ASCII domain or ends with `.` followed by that domain. |
| `regex` | Search, not full match, using ASCII case-insensitive matching and ASCII word boundaries. Anchors apply to the whole field, with no multiline mode. |

Allowed fields are `subject`, `text`, `sender_address`, `sender_domain`,
`sender_local`, the client-owned booleans, `gmail_categories`, and
`headers.<lowercase-name>` for the eight retained headers.

Regex patterns are at most 512 characters. The reviewed pattern subset uses
literals, character classes, alternation, noncapturing groups, anchors, ASCII
word boundaries, optional single atoms and bounded repeats up to 32. Unbounded
`*`/`+`, lookarounds, backreferences and quantified groups are rejected. Literal
Unicode characters, such as a curly apostrophe, match themselves. Clients must
use ASCII semantics for `\b`, `\d`, `\s` and case-insensitive matching even when
the input contains Unicode. Do not blindly use a different regex engine's
Unicode defaults. The validator is not a complete ReDoS defense for arbitrary
unreviewed feeds.

For example, `notmailchimp.com` and `mailchimp.com.example.com` do not match a
`domain_in` entry of `mailchimp.com`. A display name never authenticates a brand.

## Resolving results

1. Normalize input and evaluate every condition.
2. Return matched rule IDs in lexical order, including hints.
3. Return hint suggestions separately. Hints never set outputs, regardless of priority.
4. For each of `category`, `newsletter`, and `time_sensitive`, consider only matching decision rules that set that output. Take the highest priority.
5. If those highest-priority rules agree, return their value. Otherwise return `null` for that output and record their IDs in `conflicts`. Do not fall back to a lower priority after a conflict.
6. Return the highest-priority rule IDs in `evidence` for each considered output. Lower-priority matches remain visible in `matched_rules`.

This makes flags independent: a conflict in category need not discard an
unambiguous urgency flag. All outputs start unknown. A category name never
implicitly sets either flag.

| Priority | Initial policy |
| --- | --- |
| 100 | Actionable security, authentication and payment failures |
| 90 | Verified personal correspondence |
| 85 | Supported individual action request |
| 80 | Routine transactions |
| 75 | Calendar and policy notices |
| 70 | Promotional offers |
| 60 | Routine social notifications or explicit action-required flag |
| 55 | Newsletters |
| 20 | Optional Gmail category fallback |
| 0 | Hints only |

These numbers express precedence, not probabilities or confidence scores.
Routine receipt rules explicitly set both flags false. Security rules can
override those values; promotional subscription rules can set newsletter true
while keeping marketing urgency false.

## Releases and personal preferences

Rule changes can alter classifications and need a ruleset version bump.
Breaking format or semantic changes need a new `format_version`. Pin releases
or immutable commits; never automatically execute code supplied by a list.

An embedding client should resolve explicit message corrections first, personal
sender overrides second, then community decisions. Weak hints and unresolved
cases can reach a local learner or review queue. Overrides should be scoped to
the user, and may intentionally differ from these public defaults. None of that
personal state belongs in the public rules repository.
