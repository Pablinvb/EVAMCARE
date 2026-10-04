"""Fail-closed Render staging entrypoint; never prints configuration values."""
import os
import sys

def main():
    required=('DATABASE_URL','DERMASCAN_BOOTSTRAP_ADMIN_EMAIL',
              'DERMASCAN_BOOTSTRAP_ADMIN_PASSWORD','DERMASCAN_REFERRAL_TOKEN_SECRET',
              'DERMASCAN_PARTNER_API_KEY')
    missing=[name for name in required if not os.getenv(name)]
    # Bootstrap becomes optional once the owner explicitly marks provisioning complete.
    if os.getenv('DERMASCAN_BOOTSTRAP_COMPLETE')=='true':
        missing=[name for name in missing if not name.startswith('DERMASCAN_BOOTSTRAP_ADMIN_')]
    if missing:
        print('Staging configuration required: '+', '.join(missing),file=sys.stderr)
        return 1
    if os.getenv('DERMASCAN_POSTGRES_SCHEMA')!='evamcare_staging':
        print('Staging requires its isolated evamcare_staging schema.',file=sys.stderr)
        return 1
    if os.getenv('DERMASCAN_POSTGRES_SSLMODE','verify-full')!='verify-full':
        print('Staging requires verified PostgreSQL TLS.',file=sys.stderr)
        return 1
    import uvicorn
    uvicorn.run('backend.main:app',host='0.0.0.0',port=int(os.getenv('PORT','8000')))
    return 0

if __name__=='__main__':
    raise SystemExit(main())
