# Supabase verification — 2026-10-04

Project: EVAMCARE (`inshzjzlcwklaxpxcpve`). No credentials are recorded here.

## Executed against the real project

- Applied `skin_records` migration from the prepared SQL.
- Executed `supabase/tests/authorization.sql` successfully, including ownership, administrator clinical denial, evaluator assignment, professional scopes, notes, expiry, revocation and private Storage access.
- Fixtures were rolled back: zero fictional test users remain.
- Verified 11 tables with RLS enabled, 11 policies and a private `evamcare-photos` bucket.
- Applied supplementary migration `restrict_auto_rls_helper`: `REVOKE EXECUTE ON FUNCTION public.rls_auto_enable() FROM PUBLIC, anon, authenticated;`. This platform-generated event-trigger helper must not be callable by API clients. Event-trigger operation is unchanged.
- Security advisors have no WARN/ERROR findings. The INFO finding for audit_logs without a client policy is intentional: client access is denied.

## Deployment gate — not yet passed

Render still serves commit b0afce1, version 0.9.0. Its health check does not verify PostgreSQL. The runtime `evamcare_local` schema is not present in this project; no Render-to-Supabase connection has been demonstrated.

The prepared `evamcare` schema uses Supabase Auth identities. The current FastAPI implementation uses local opaque sessions and a separate private `evamcare_local` schema. SQL RLS tests are not evidence of a real administrator login or of local sessions mapping to Supabase Auth.

Before replacing production, run the branch in a separate staging runtime with DATABASE_URL supplied privately, verify version 0.10.0 health reports PostgreSQL, run API authentication/authorization tests, and have the owner perform the first administrator login. Never copy credentials into CI logs, repository files or chat.

After that successful administrator login, remove DERMASCAN_BOOTSTRAP_ADMIN_EMAIL and DERMASCAN_BOOTSTRAP_ADMIN_PASSWORD from the runtime configuration and verify login again. Do not remove them before provisioning has been verified.
