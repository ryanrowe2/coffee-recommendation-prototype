# Original Prototype vs. Production Proposal vs. This Repository

This matrix was developed after examining the original Python demo and the technical portions of an internal planning document. The original internal document is **not included**; confidential commercial arrangements, vendor negotiation details, pricing and customer-identifying implementation data have been omitted.

| Area | Earlier Python prototype | Original production proposal | Standalone portfolio build |
|---|---|---|---|
| Backend | One-file Flask implementation | Refactor/extend Flask integration | Modular Flask application factory and routes |
| Questionnaire | Typeform webhook intake | Typeform embedded in Shopify | Local browser form plus signed mock Typeform webhook |
| Input mapping | Field-ref extraction and string cleanup | Strict contract for coffee preferences | Bounded vocabulary, aliases, rejected malformed values |
| Authentication | Optional webhook HMAC verification | Mandatory signature validation | Signature required for any external webhook; blocked if unconfigured |
| Ranking | Weighted deterministic scorer | OpenAI selects three eligible catalog entries | Deterministic weighted scorer with explainable contribution breakdown |
| Model output | Not applicable | Structured JSON, strict candidate keys, validated retries | Not applicable: no OpenAI calls |
| Catalog | Three demonstration products | Active/seasonal real product eligibility | Nine wholly synthetic records, eight active; three caffeine-compatible choices per option, strict catalog validator |
| Availability | No eligible-product filtering | Active and monthly availability flags | Manual `active` flag only; no live inventory |
| Persistence | JSON files, raw payloads | Persistent records and duplicate state | SQLite records with catalog digest/version, no raw payloads, webhook and browser-form idempotency |
| API | Health, preview and saved result retrieval | Shopify-readable result contract | Health, validated preview, stored result retrieval |
| Results | Flask-built HTML cards | Shopify/Liquid storefront rendering | Responsive Jinja results cards, accessible locally |
| Cart | Shopify-style cart URL assembly | Native Shopify Ajax add-to-cart | Illustrative, **non-functional** synthetic cart URLs |
| Feedback | Not implemented | User feedback associated with recommendation | Not implemented; documented future integration |
| Debugging | Public debug retrieval routes | Disable/protect debug endpoints | Debug retrieval routes removed |
| Security | Broad demo defaults and limited bounds | Explicit webhook/CORS/deployment safeguards | Strict payload limit, canonical HTTPS CORS allowlist, CSP, CSRF and form nonce, loopback serving |
| Deployment | Waitress serving | Stable production backend and storefront integrations | Documented local Waitress execution and CI definition |
| Automated QA | Not supplied | Integration/acceptance QA workstream | Pytest pure modules and Flask integration tests |
| Screenshots | No authorized storefront screenshots supplied | Shopify theme results intended | Screenshots of actual local Jinja render outputs |

## Acceptance criteria satisfied by the local build design

- Structured preferences can be submitted locally, normalized, scored, persisted and retrieved through JSON.
- Three eligible, ranked products are returned with scores and human-readable reasons.
- Synthetic catalog validation and active flag filtering are deterministic.
- Mock Typeform signed-webhook requests, duplicate tokens, and conflicting tokens are handled in code and covered by tests.
- Responsive results cards and illustrative cart links use no protected customer assets.
- Configuration and failure-path behavior are documented, with CI configured for execution after publication.

## Not claimed as completed

Live storefront embedding, Typeform administration, OpenAI inference, model-output validation/repair, genuine Shopify checkout, validated live variant IDs, customer feedback, client delivery, production deployment, revenue impact, and real-user conversion improvements. These require evidence and access that are outside the independent local demonstration.

The production proposal explicitly used storefront-rendered results; the Flask/Jinja results page here is a deliberate **local portfolio adaptation**, not evidence that the original production UI was delivered.
