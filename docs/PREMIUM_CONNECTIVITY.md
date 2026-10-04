# Premium interface and connectivity audit

## Verified on 2026-10-04

- GitHub Pages config.js and repository variable BACKEND_API_URL both point to https://dermascan-ai-api.onrender.com over HTTPS.
- Render serves b0afce1 / 0.9.0, not the development PostgreSQL implementation.
- Health returned HTTP 200. Login exists in deployed OpenAPI.
- Login OPTIONS preflight returned HTTP 200 with access-control-allow-origin https://pablinvb.github.io and Content-Type / Authorization / X-Patient-ID allowed.
- Browser inspection of the public page showed no captured JavaScript errors. Failed to fetch was not reproduced; a historic exact cause cannot be asserted from current evidence. A transient timeout / cold start remains a possibility, not a proven diagnosis.
- Render logs API returned 503 because its Loki provider returned 502. No credentials were retrieved.
- Supabase prepared evamcare schema exists but has zero user profiles/admin roles. Runtime evamcare_local schema is absent. This does not prove whether an administrator exists in production SQLite.

## Implemented

Shared forest / cream / sage / lime design tokens and components in assets/premium.css; split desktop access screens and stacked mobile CSS; password visibility toggle; safe field rendering; retained original logo and scanner. Hero metrics explicitly labelled illustrative. Network errors use understandable Spanish; account GET retries once, request timeout 25 seconds; POST is not automatically replayed to avoid duplicate actions. Re-submitting the enabled login button is the explicit retry mechanism. Connection status now requires a successful health response and includes a retry button. It does not claim partner availability merely because an API URL exists.

## Release gates / limitations

Staging still needs privately provisioned DATABASE_URL and bootstrap credentials. No verified real administrator login or Render-to-Supabase connection yet. Supabase Auth RLS tests are separate from active local opaque-session authorization. Do not replace production until staging checks pass and the owner explicitly approves replacement. Remove bootstrap variables only after the first verified administrator login and verify login again.

SMTP invitation/reissue, real partner agendas and verified live catalog integrations remain dependencies rather than implied by the status indicator. Existing dashboard tools receive shared styling; aggregate user summary cards and clinically defined pending-followup scheduling are not completed. Desktop preview inspected; mobile rules are implemented but mobile browser validation is pending because viewport control is unavailable in this session.
