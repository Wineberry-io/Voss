# Laravel Account and Control-Plane Plan

**Status:** Proposed future milestone
**Saved:** 2026-08-30
**Implementation:** Not started

## Goal

Add an optional Voss account shared by the website and desktop application without weakening Voss's local-first behavior or uploading provider credentials, repository content, or prompts by default.

## Locked Direction

- `www.tryvoss.dev` remains the static Next.js marketing site.
- `account.tryvoss.dev` hosts the Laravel account UI and versioned API.
- Laravel 13 and PHP own identity, account data, email, OAuth, future billing, and future team-control-plane data.
- PostgreSQL is the hosted system of record.
- The Laravel web UI uses the official React/Inertia starter kit.
- The desktop application authenticates through the system browser using Authorization Code with PKCE.
- Voss account authentication remains separate from Anthropic, OpenAI, Claude, and Codex provider authentication.
- Local terminal, harness, sessions, and memory remain usable while signed out or offline.

## Authentication Boundaries

| Boundary | Responsibility |
|---|---|
| Voss account auth | Laravel identity and future entitlements |
| Provider auth | Local Claude, Codex, Anthropic, and OpenAI credentials |
| Sidecar auth | Ephemeral local loopback bearer token |

## Phase 0 — Account and Trust Contract

### Outcome

Lock product, privacy, security, and architecture decisions before implementation.

### Deliverables

- Decide whether accounts are optional or required; default recommendation is optional.
- Lock service location as `services/control-plane/`.
- Lock domains and API versioning.
- Define the cloud-data allowlist and prohibited data.
- Define account deletion, token revocation, retention, and recovery behavior.
- Write the OAuth threat model and initial OpenAPI contract.
- Select token lifetimes and desktop callback mechanism.

### Exit Gate

- Every stored cloud field has a consumer and retention rule.
- Threat model covers token interception, malicious callbacks, CSRF, enumeration, leaked refresh tokens, and log leakage.
- Raw code, prompts, provider credentials, and local session content are excluded unless a later decision explicitly allows them.

## Phase 1 — Laravel Control-Plane Foundation

### Outcome

Create a deployable Laravel service without product-specific account behavior.

### Deliverables

- Laravel 13 application under `services/control-plane/`.
- Official React/Inertia starter kit.
- PostgreSQL development, test, and production configuration.
- `/up` health endpoint.
- Database-backed queues.
- Safe local transactional-email configuration.
- CI for Composer install, frontend install/build, formatting, static analysis, migrations, and tests.
- Environment example with placeholders only.
- Structured logging that excludes credentials and authorization headers.
- Staging deployment configuration once a hosting target is selected.

### Scope Fence

- No Passport.
- No desktop changes.
- No billing, teams, entitlements, Redis, or sync.
- No deployment-provider coupling until hosting is selected.

### Exit Gate

- Clean install, migration, frontend build, and test suite pass.
- Health check passes in a production-like environment.
- Production configuration rejects debug mode and insecure cookie settings.
- Logs contain no passwords, authorization codes, or tokens.

## Phase 2 — Web Signup and Account Management

### Outcome

Make `account.tryvoss.dev` the browser identity surface.

### Deliverables

- Registration, login, logout, email verification, and password reset.
- Profile and password updates.
- Account deletion.
- Login and reset rate limits.
- Secure HTTP-only session cookies and CSRF protection.
- Static-site Sign up and Log in links to Laravel.
- Signed-in account landing page.

### Exit Gate

- Registration through verification and login passes end to end.
- Reset links are expiring and single-use.
- Deleted accounts cannot authenticate: deletion revokes every session, access token, and refresh token immediately, and `/api/v1/me` checks account status on every call. No grace period.
- Errors do not reveal whether an email exists.
- Marketing site remains a static export.

## Phase 3 — Desktop OAuth and Account API

### Outcome

Expose secure native-app authorization and the minimum account API.

### Deliverables

- Laravel Passport public client.
- Authorization Code with PKCE; no embedded client secret.
- One-time `state` validation and an exact registered callback.
- Scopes: `account:read` for `/api/v1/me`; `account:revoke` for the revocation operations below. Revocation endpoints reject tokens that lack the scope; negative scope tests cover both.
- Short-lived access tokens (≤ 15 minutes) and rotating refresh tokens: every refresh issues a new refresh token and invalidates the old one. Reuse of a consumed refresh token revokes the whole token family. Families have an absolute lifetime (30 days) regardless of refresh activity. The Rust client tests cover replay, expiry, and refresh.
- `GET /api/v1/me`.
- Current-token and all-device revocation operations, both under `account:revoke`.
- Authorized-session management page.
- Versioned API error envelope.

### Scope Fence

- No password grant.
- No desktop password collection.
- No Sanctum password-to-token endpoint.
- No wildcard redirects.
- No provider-credential endpoints.

### Exit Gate

- Valid PKCE flow succeeds.
- Missing or incorrect verifier, state, callback, or reused code fails.
- Revoked credentials cannot access `/api/v1/me`.

## Phase 4 — Rust Account Client

### Outcome

Implement the reusable native account client separately from provider authentication.

### Deliverables

- New `crates/voss-account` crate.
- PKCE and cryptographically random state generation.
- System-browser launch and callback handling.
- Token exchange, refresh, and revocation.
- Typed `/api/v1/me` client.
- Credential-store abstraction backed by OS-secure storage.
- Redaction-safe errors and debug output.

### Exit Gate

- Mock-server Rust tests cover login, refresh, revocation, timeout, and malformed responses.
- State and verifier are never persisted.
- Tokens never appear in logs, errors, or debug output.

## Phase 5 — Tauri Desktop Integration

### Outcome

Expose optional account login without blocking local use.

### Deliverables

- Tauri opener, deep-link, and single-instance support.
- Account settings surface.
- Signed-out, signing-in, signed-in, offline, expired, and revoked states.
- Browser-based sign-in.
- Rust-owned callback validation.
- Profile display, logout, and revoke-all behavior.
- Bounded background refresh.

### Exit Gate

- Login and logout pass on supported macOS, Windows, and Linux targets.
- Malformed and manually triggered callbacks are rejected.
- A callback delivered to a second process reaches the running app safely.
- Desktop startup and local work remain available offline and signed out.
- Existing provider authentication remains unchanged.

## Phase 6 — Public-Launch Hardening

### Outcome

Prepare the identity service for untrusted public traffic.

### Deliverables

- Authentication-event audit records.
- Global and per-account abuse limits.
- Email-delivery monitoring.
- Backup and restore process.
- Session-management UI.
- Account-deletion and retention jobs.
- Security headers and CSP.
- Dependency and secret scanning.
- Recovery and abuse-response runbooks.
- Production alerting for authentication and email failures.
- Privacy policy matching actual collection.

### Exit Gate

- Backup restore is exercised successfully.
- Revoke-all invalidates every refresh path.
- Deletion matches the retention contract.
- Automated checks find no authorization headers or tokens in logs.
- No high-severity threat remains open.

## Phase 7 — Entitlements and Billing

### Outcome

Support paid cloud capabilities only after a real paid feature exists.

### Deliverables

- Stripe Cashier integration.
- Server-owned products, prices, and entitlements.
- Idempotent webhook processing.
- `/api/v1/entitlements`.
- Last-known desktop entitlement cache and explicit offline-grace policy.
- Billing portal and cancellation, payment-failure, refund, and restoration handling.

### Exit Gate

- Checkout through cancellation and expiration passes end to end.
- Duplicate and out-of-order webhooks are safe.
- Clients cannot grant themselves entitlements.
- Billing outages do not disable local features.

## Phase 8 — BOS and Team Control-Plane Integration

### Outcome

Connect accounts to shared teams and projects after BOS identity and read-model boundaries exist.

### Deliverables

- User, organization, project, and membership model.
- Desktop-node registration and explicit project linking.
- Allowlisted BOS metadata upload.
- Team/project authorization policies.
- Device and membership revocation.
- Integration with BOS7, BOS8, and BOS16 rather than a parallel control plane.

### Exit Gate

- Users see only authorized organizations and projects.
- Membership removal immediately blocks shared access.
- Network fixtures contain no repository content, prompts, or provider tokens.
- Desktop local execution continues while disconnected.

## Recommended MVP Cutoff

Ship Phases 0–6 first. Defer billing, entitlements, teams, and sync until a concrete paid or shared-control-plane capability requires them.
