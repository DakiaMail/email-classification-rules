# Attribution

Selected English phrases, public sender-domain examples and header signals are
adapted from [gmail-inbox-cleaner](https://github.com/kbridgie01/gmail-inbox-cleaner),
by Kiera Bridgeman (`kbridgie01`), at revision
[`37ef90b3851416551f2a92130608860ee7feade6`](https://github.com/kbridgie01/gmail-inbox-cleaner/tree/37ef90b3851416551f2a92130608860ee7feade6).

The original MIT license is preserved verbatim in
[third_party/gmail-inbox-cleaner.LICENSE](third_party/gmail-inbox-cleaner.LICENSE).
Its copyright notice is also retained in this repository's [LICENSE](LICENSE).

| Upstream source | Adaptation here |
| --- | --- |
| `RetailAnalyzer.ts` | Retail phrases used as combined Promotions evidence, without importing numeric confidence scores. |
| `NewsletterAnalyzer.ts` | Newsletter/digest wording and subscription evidence, with separate category and newsletter outputs. |
| `HeaderAnalyzer.ts` | List, unsubscribe and bulk-header evidence; headers alone remain hints. |
| `OrderReceipt.ts` | Order, shipping, receipt and invoice vocabulary, tightened into transaction decisions. |
| `VetoRules.ts` | Authentication, security and transaction vocabulary, separated into Primary and Transactions instead of a shared exemption. |
| `ProtectedSenders.ts` | Calendar and notification vocabulary; blanket company protections and loan-offer exemptions were not carried over. |
| `CustomSenderLabels.ts` | Selected public social-service domains, requiring authentication and notification context for a decision. |
| `SenderAnalyzer.ts` | Delivery-platform examples and no-reply evidence, reduced to hints with domain-boundary checks. |

These filenames are under upstream `src/services/classifier/`. Each rule names
its source records in `rules/core.json`. New priority resolution, action-request
policy, correspondence handling, provider fallbacks, matching contract, matcher
and synthetic examples are DakiaMail contributions. Patterns were adapted,
combined and narrowed; upstream classification behavior is not preserved.

The upstream default advertising and newsletter sender lists are empty
templates and contributed no populated sender dataset. Its mailbox access,
deletion, labeling, export and dependency code is not included. This is an
independent project and does not imply upstream endorsement.
