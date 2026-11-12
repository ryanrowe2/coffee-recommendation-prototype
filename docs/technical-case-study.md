# Technical Case Study: From Coffee Quiz Prototype to Reproducible Local Application

## 1. Project overview

The original technical starting point was a Flask-based coffee recommendation demonstration with a Typeform-compatible webhook, simple three-product catalog, deterministic matching rules, HTML recommendation rendering, local JSON persistence, and Shopify-style link construction. Separately, an internal technical plan explored a more advanced production storefront and AI architecture. This repository turns the **demonstrable local functionality** into a coherent, standalone engineering artifact.

The resulting application is called **Coffee Atlas**, an entirely synthetic demonstration. It is neither the original commerce storefront nor a claim of production delivery.

## 2. Business problem and intended customer experience

Coffee customers frequently describe their tastes in loosely structured terms: preferred roast, brew method, flavor notes, caffeine needs and milk habits. A recommendation workflow can convert those signals into a small, understandable product shortlist. A successful experience needs repeatable answers, understandable match reasons, product eligibility rules and a reliable path from questionnaire to result.

The local experience follows the essential story: express preferences → normalize data → score eligible coffee products → see three ranked results and explanations.

## 3. Prototype objectives

The engineering objective was to keep the useful algorithm and webhook shape while improving isolation, safety, portability and observability. The selected scope: standalone Flask application, synthetic catalog, local form/results experience, JSON API, transaction-safe persistence, signed mock webhook example, automated tests and clear documentation.

## 4. Requirements and constraints

- No access to the historical Shopify storefront, official product assets, operational inventory, real Typeform account, or AI billing account.
- No publishing internal partner documents or private store identifiers.
- A clean environment should run the local demo once its Python dependencies are installed.
- Results should be deterministic, valid, testable and explainable.
- External URLs must remain **illustrative** rather than misleading purchase CTAs.
- Business scope documents should distinguish delivered prototype engineering from proposed production architecture.

## 5. Application architecture

A Flask application factory initializes immutable config, validates the synthetic catalog, creates SQLite storage and registers routes. Pure modules own preference normalization, scoring, catalog validation and HMAC verification. Web boundaries parse untrusted data and return documented HTTP outcomes. Server-rendered Jinja templates provide the visible demonstration. See [architecture](architecture.md) for a component diagram and data contracts.

The architecture uses small modules only where responsibilities create useful independent test seams; it does not introduce a service framework, message bus, ORM, or model abstraction.

## 6. Data flow and API contracts

Two ingestion paths feed the same scorer:

1. **Local demonstration:** HTML form → session CSRF validation → database-backed form nonce → strict preference mapping → ranking → SQLite write → `303` → HTML results.
2. **External webhook simulation:** raw signed JSON → HMAC verification → stable Typeform field refs → mapping → ranking → SQLite idempotency check/write plus catalog-versioned snapshot → JSON acknowledgement.

`GET /api/recommendations/<response_id>` provides sanitized structured results for integration consumers. No raw webhook JSON, free-form notes, or contact data appear in stored records or result responses.

A missing external webhook secret explicitly disables webhook intake. Normalized answer fields are whitelist-based; invalid values and ambiguous duplicate refs are rejected rather than silently coerced.

## 7. Recommendation algorithm

The deterministic scorer awards points for matching attributes: roast `+5`, brew method `+4`, caffeine `+3`, milk preference `+2`, each shared flavor note `+3`, and an explicit style choice `+2`. Catalog entries marked inactive are never considered, and a selected caffeine level restricts candidates to compatible coffees before scoring. Scores sort descending with title and stable product key tie-breaks; the top three are returned.

Each recommendation includes a per-attribute contribution map and a reason constructed from the attributes actually matched. When no requested trait matches, the product is labeled an exploratory alternative rather than a personalized match. Free-text notes are never inferred as likes/dislikes or used in scoring.

This approach is transparent and reproducible. It does not learn user preferences, optimize against observed conversion, or estimate subjective satisfaction; the scoring constants are authored heuristics.

## 8. Technical implementation

The portfolio refactor replaces global import-time side effects with a factory, validates catalog structure before serving, uses SQLite transactions rather than mutable JSON files, requires webhook signatures and controlled identifiers, removes public debug endpoints, and separates templates/styles from Python route functions. Nine fictional products, including three active decaf options and one inactive seasonal entry, support truthful top-three recommendations for all caffeine settings.

Product illustrations are local inline SVG and CSS. Variant identifiers are synthetic and product URLs use the reserved `.example` domain. The generated Shopify-style cart URLs demonstrate formatting only and are copyable examples, **not checkout actions**.

## 9. Testing and validation

The repository includes tests for caffeine eligibility, structured style selection, order-insensitive fingerprints, catalog digest provenance, concurrent local-form idempotency, path symlinks, Unicode and accessibility contrasts, as well as vocabulary/alias normalization, malformed payloads, Typeform field refs, HMAC signing and tampering, catalog schemas, stable rank order, tie behavior, match explanations, absent/duplicate submissions, SQLite persistence, and injection-shaped identifiers. Its Flask endpoint, advertised Waitress subprocess and real-Chromium browser tests additionally exercise form CSRF, browser redirects, health endpoints, signed webhooks, idempotent replays, API lookup, debug-route absence, payload limits, HTML and CORS controls.

The final exact-archive local certification executed Flask, HTTP, Waitress and Chromium suites with **264 tests and zero skips**. Following publication, the final protected-branch [GitHub Actions run](https://github.com/ryanrowe2/coffee-recommendation-prototype/actions/runs/43185857273) passed all four required jobs (Python 3.11/3.12/3.13 and Chromium), **265 tests with zero skips**, and **95.16% application coverage**. It uploaded six live-server browser screenshots and a machine-readable release report. See [v1.0.3 local certification history](maintenance-verification-v1.0.3.md) for local commands and evidence; [archived v1.0.0 verification](final-verification.md) is retained separately.

## 10. Original production architecture proposal

The earlier architectural plan anticipated a Shopify/Liquid storefront quiz with embedded Typeform, on-submit response routing, a Flask webhook, backend-controlled eligible catalog, constrained OpenAI ranking of exactly three known products, strict output validation, stored results, Shopify-native Ajax cart interactions and feedback capture. The production result page would be a storefront component, not Flask HTML.

That design would require authorized access, verified identifiers, a real product catalog and an operational deployment. It remains an **unimplemented design proposal** in this repository.

## 11. Engineering tradeoffs

- **Deterministic vs. AI:** reliable local ranking eliminates account and API dependencies, but does not demonstrate real model integration or semantic personalization.
- **SQLite vs. service database:** lean durability and restart-safe duplicate detection are ideal for local demonstration; concurrency and operational scaling need evaluation for a public workload.
- **Strict vocabularies vs. flexibility:** explicit contracts improve reliability and tests; new Typeform wording requires deliberate alias updates.
- **Jinja UI vs. storefront ownership:** the local experience is inspectable without Shopify access but cannot validate a Liquid theme or native cart operations.
- **Illustrative URLs vs. live e-commerce:** preserved integration reasoning without disclosing proprietary variant identifiers or misleading customers into checkout.

## 12. Operational considerations

The server binds only to loopback by default. A local/production mode flag disables demo-only endpoints outside local mode; production configuration checks secret length and expected form ID. A request body cap, no-default CORS, CSP, security headers, CSRF, restricted response identifiers and generic error messages reduce easy trust-boundary failures. SQLite records persist until manually deleted, so the app is only suitable for synthetic test data without a separately designed data lifecycle.

For production, further engineering is required: identity/privacy review, retention/deletion policy, authentication for read access, throttling, deployment TLS/reverse proxy, health monitoring, backup/recovery, secret management, operational logs and authorized storefront security testing.

## 13. Limitations

No real client products or prices, real checkout, production storefront UI, AI rankings, custom Shopify app, real survey-account configuration, customer feedback, analytics, measured conversion improvement, deployment history or production reliability claims. The local screenshots document rendered code and not a production storefront. The exact **v1.0.3** local archive passed Flask, Waitress, real HTTP and Chromium tests with **264 passing tests and zero skips**; see [local verification](maintenance-verification-v1.0.3.md). The current published revision passed the [hosted strict release gate](https://github.com/ryanrowe2/coffee-recommendation-prototype/actions/runs/43185857273) with **265 tests, zero skips, and 95.16% application coverage**.

## 14. Potential future enhancements

The published Python matrix and Chromium gate have been verified on protected `main`. Optional future work may consider a small feedback endpoint, better retention controls, accessibility testing, a validated catalog update process, or externally integrated recommendations—each added in response to a demonstrable requirement rather than for feature count.

## Engineering significance

This project tells a clear technical story: transform ambiguous taste inputs into a bounded data contract; select products through a reproducible scoring system; protect webhook and persistence boundaries; expose stable, inspectable APIs; deliver a useful local UI; and document exactly where a commercial architecture would demand additional authorization and integration work.
