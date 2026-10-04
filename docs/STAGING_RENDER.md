# EVAMCARE isolated free staging

URL: https://evamcare-staging.onrender.com

Render service: srv-db17jgp42hec73edj0ng, free Python web service, branch codex/security-persistence. Manual deployments only. Production service srv-d8t86o77f7vs73bupqtg is unchanged.

## Enter privately in Render Environment

Required before the first successful startup:

- DATABASE_URL: EVAMCARE Supabase Session pooler connection (port 5432, IPv4), including the password. Do not use the transaction pooler.
- DERMASCAN_BOOTSTRAP_ADMIN_EMAIL: your staging administrator email, preferably a fictional/test account.
- DERMASCAN_BOOTSTRAP_ADMIN_PASSWORD: a unique test password, 12–256 characters.
- DERMASCAN_REFERRAL_TOKEN_SECRET: long random secret exclusively for staging.
- DERMASCAN_PARTNER_API_KEY: long random secret exclusively for staging.

Already configured: production security mode, verified TLS, private evamcare_staging schema, Supabase project URL, exact staging CORS origin. Never point staging at the production schema. First startup creates the compatible runtime tables and enables RLS, denying direct Data API client access. Active local-auth checks remain in FastAPI. The separately prepared evamcare Supabase Auth schema is not its identity provider.

Optional private photograph tests: SUPABASE_SERVICE_ROLE_KEY (server only). SUPABASE_URL is already configured. No images are stored without explicit consent.

Optional recovery email tests: DERMASCAN_SMTP_HOST, DERMASCAN_SMTP_PORT=587, DERMASCAN_SMTP_FROM, DERMASCAN_SMTP_USER, DERMASCAN_SMTP_PASSWORD, DERMASCAN_RECOVERY_URL=https://evamcare-staging.onrender.com/ . STARTTLS is mandatory. Invitation email remains a separate pending feature.

## Optional fictional demos

Set DERMASCAN_STAGING_DEMO=true and configure three private password secrets:
DERMASCAN_DEMO_EVALUATOR_PASSWORD, DERMASCAN_DEMO_PATIENT_PASSWORD, DERMASCAN_DEMO_PROFESSIONAL_PASSWORD.

Accounts: evaluator@evamcare.example.test, patient@evamcare.example.test, professional@evamcare.example.test. Administrator uses the privately configured bootstrap account. The patient is explicitly fictional. The evaluator is assigned that patient; professional sharing expires after 24 hours and can be revoked by the patient. No synthetic scan is presented as a real evaluation. Seeder is idempotent and never resets existing passwords, reactivates accounts or renews revoked/expired access.

After first successful administrator login: set DERMASCAN_BOOTSTRAP_COMPLETE=true, remove both DERMASCAN_BOOTSTRAP_ADMIN_* secrets and verify login after redeploy. Disable DERMASCAN_STAGING_DEMO and remove the three demo passwords after provisioning; existing accounts persist in PostgreSQL.

## Verification status

Service created; database connection and real staging authentication are pending secret entry. Until then startup deliberately fails closed rather than falling back to SQLite. Existing Supabase Auth RLS suite was rerun successfully with rollback. CI and local fixture tests do not replace real staging login and browser journeys. Production publication requires separate owner approval.
