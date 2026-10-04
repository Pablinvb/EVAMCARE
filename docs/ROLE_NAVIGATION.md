# Role navigation

Development branch: codex/security-persistence. Production is not automatically replaced.

The existing scanner, account API, patient directory, assignments, grants, private photos and password recovery are reused. Hash routes work on GitHub Pages without a server rewrite:

- `#/`: public welcome; patient demo and account forms hidden.
- `#/login`: email and password only, with recovery/activation links.
- `#/activate-account?token=…`: invitation is checked by POST; the fragment is immediately cleared and the secret stays in memory. Password confirmation, expiry and single use are enforced. Reload without a token requires reopening the private invitation.
- `#/forgot-password`: email only; generic server response.
- `#/reset-password`: password confirmation, recovery token and existing session revocation. Existing `#reset=…` email links remain supported.
- `#/panel`: authorized role chooser, using `/accounts/me`, not browser role claims.
- `#/{admin,evaluator,patient,professional}/dashboard`: role-specific sidebar and reused tools.
- Additional role pages: users, patients, evaluators, professionals, new-patient, record, sharing, grants and settings as applicable.

Backend checks remain mandatory. UI routing does not grant access. Administrators do not automatically receive clinical access. Evaluator reevaluation retains selected patient ID and requires consent. No tables or existing patient records are removed.

## Remaining dependencies / limitations

- Invitation email sending and reissue are not implemented: authorized staff receive a private activation link for manual delivery. Invalid-link screen directs the user to the inviter; password recovery is not a replacement for pending-account invitation reissue.
- SMTP and private storage credentials are still deployment dependencies.
- Evaluator recent evaluations are shown as last evaluation and scan count in the directory. There is no clinically defined reevaluation-due scheduler; no fabricated pending appointments are shown.
- The administrator evaluations section explains clinical restrictions; aggregate evaluation reporting is not implemented.
- Record fields are rendered safely as structured cards; specialized metric charts and a dedicated latest-scan summary still need further UI refinement.
- RLS Supabase Auth schema and active local-auth backend remain separate, as documented in PRODUCTION_ACTIVATION.md.
- Real production login and all 14 browser journeys must be validated in staging before release. Local API tests are not proof of a real production administrator login.

## Publish

Run SQLite and PostgreSQL CI, container build and staging role journeys before merging PR #2. Configure SMTP recovery URL to the frontend (legacy fragment links are supported). Publish the entire assets directory including navigation.js; no separate physical /login file is required. Do not switch the existing Render service until staging authentication and PostgreSQL checks pass.
