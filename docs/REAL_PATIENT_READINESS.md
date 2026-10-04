# Real-patient pilot gates

Owner-supplied controller: Pablo Vega. Privacy contact: pablodanielvegabailonjw@gmail.com.
Owner confirmed minimum one year of record retention; after the first year, three months without activity makes a record eligible for deletion. Backups retention is not yet defined. No automatic deletion job is enabled.

## Controls implemented in development

- History routes now require authorized bearer context for registered patients. Invalid bearer plus an internal patient session cannot bypass access checks.
- Professionals only list active, non-expired grants; record/photo scopes remain checked by FastAPI.
- Each authorized evaluation records a versioned consent receipt. Two scans of an assigned patient retain the same patient ID without creating a duplicate profile.
- Versioned public privacy notice, patient consent/revocation, own-record export, reauthenticated erasure request. Request immediately revokes sessions, evaluators and professional/public shares and deactivates the patient account; it does not claim physical deletion is already done.
- Operator `python -m backend.erase_patient --request-id … --confirm-reviewed` completes an explicit request, removes optional private photos before database data, purges dependent patient records transactionally and retains a minimal erasure tombstone for restore suppression. No production request is executed during tests.
- New account invitations have explicit test/real dataset labels. Real accounts are blocked in staging and disabled by default everywhere. Existing accounts are unclassified until reviewed; staging synthetic accounts must never be imported into a production schema.
- Added PostgreSQL dump/restore exercise to CI using fictional data in a separate database. Not a backup of real data, not a disaster-recovery guarantee.

## Not yet ready for real people

Controller must review the final notice, rights process, processor/cross-border arrangements, purpose-specific consent and adult-only admission. Draft text is not legal approval. Adult restriction is informational at present; an age verification workflow remains pending. Evaluator checkbox is an attestation, not proof of signed patient consent.

Configure DERMASCAN_PRIVACY_CONTROLLER, DERMASCAN_PRIVACY_CONTACT and DERMASCAN_RETENTION_POLICY. Do not enable DERMASCAN_REAL_PATIENTS_ENABLED until readiness checks and owner release approval. New dataset labels do not by themselves replace separate production/staging schemas or full authorization.

Supabase free plan does not offer downloadable managed database backups. Official guidance recommends regular logical dumps and off-site copies: https://supabase.com/docs/guides/platform/backups . Do not call the active database a backup. A private Storage bucket in the same Supabase project can hold encrypted dumps if owner chooses, but cannot protect against total project/account loss and needs separately controlled encryption keys and retention. Storage photo bytes are not included in pg_dump.

Before production: choose backup retention and destination, configure scheduled encrypted snapshots without printing DSNs, verify a restore to an isolated database (rows, RLS, accounts, grants and consent), reapply erasure ledger and revoke restored sessions, and document recovery time/data-loss objectives. Never restore over the live database. No paid services have been purchased.
