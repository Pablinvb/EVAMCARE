"""CI-only restore verification. Never connect this fixture to real databases."""
import os
import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict

settings=conninfo_to_dict(os.environ['DATABASE_URL'])
assert settings.get('dbname')=='evamcare_test' and settings.get('host')=='localhost'
schema='evamcare_local_ci'
def fingerprint(database):
    with psycopg.connect(**{**settings,'dbname':database}) as c:
        tables=c.execute('SELECT tablename,rowsecurity FROM pg_tables WHERE schemaname=%s ORDER BY tablename',(schema,)).fetchall()
        counts=[(name,rls,c.execute(sql.SQL('SELECT count(*) FROM {}.{}').format(sql.Identifier(schema),sql.Identifier(name))).fetchone()[0]) for name,rls in tables]
        for role in ('anon','authenticated'):
            assert not c.execute('SELECT has_schema_privilege(%s,%s,\'USAGE\')',(role,schema)).fetchone()[0]
        return counts
assert fingerprint('evamcare_test')==fingerprint('evamcare_restore')
