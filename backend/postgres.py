"""PostgreSQL provider for the existing local-auth API, without a second identity system.

All data resides in a private schema; callers access it through authorized FastAPI
routes. Supabase Data API roles have no grants to this schema. The prepared Auth/RLS
schema is a separate future migration, not implicitly enabled by DATABASE_URL.
"""
import os
import re
from collections.abc import Mapping
from psycopg import connect as pg_connect
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.conninfo import conninfo_to_dict

def connection_diagnostic(error):
    # Inspect driver text in memory only. Never return it: it may contain secrets.
    message=str(error).lower()
    state=getattr(error,'sqlstate',None)
    if state in ('28P01','28000') or any(s in message for s in ('password authentication failed','tenant or user not found','authentication failed','sasl authentication')):
        return 'DB_AUTH: Check pooler username, project reference and database password; percent-encode URI password once.'
    if any(s in message for s in ('could not translate host','name or service not known','nodename nor servname','getaddrinfo','name resolution')):
        return 'DB_DNS: Check the Session Pooler hostname copied from Supabase Connect.'
    if any(s in message for s in ('does not match host','hostname mismatch','certificate name')):
        return 'DB_TLS_HOST: Use the exact Session Pooler hostname; the certificate does not match the configured hostname.'
    if any(s in message for s in ('certificate verify failed','self-signed certificate','unable to get local issuer','root certificate file')):
        return 'DB_TLS_CA: Configure PGSSLROOTCERT with the trusted Supabase CA certificate file; keep verify-full enabled.'
    if any(s in message for s in ('certificate','sslrootcert','ssl error','tls','ssl connection','sslmode','root certificate')):
        return 'DB_TLS: Check Supabase CA certificate and PGSSLROOTCERT; keep verify-full enabled.'
    if any(s in message for s in ('network is unreachable','no route to host')):
        return 'DB_NETWORK: Use IPv4-compatible Supabase Session Pooler on port 5432, not the IPv6 direct endpoint.'
    if any(s in message for s in ('timeout','timed out','connection refused','could not connect')):
        return 'DB_CONNECT: Check port 5432, project status and Supabase network restrictions for Render outbound IPs.'
    if state=='3D000' or 'database' in message and 'does not exist' in message:
        return 'DB_DATABASE: Check the database name in DATABASE_URL.'
    if any(s in message for s in ('invalid dsn','invalid uri','invalid percent','missing key','invalid integer','invalid connection option')):
        return 'DB_FORMAT: Copy the PostgreSQL URI without quotes/placeholders; percent-encode password reserved characters once.'
    return 'DB_UNKNOWN: Connection rejected; inspect configuration privately without disabling TLS.'

def validate_staging_connection(url):
    try:parts=conninfo_to_dict(url)
    except Exception:
        raise RuntimeError('DB_FORMAT: Invalid DATABASE_URL syntax; check URI encoding privately.') from None
    if os.getenv('DERMASCAN_POSTGRES_SCHEMA')=='evamcare_staging':
        host=parts.get('host','')
        if not host.endswith('.pooler.supabase.com'):
            raise RuntimeError('DB_ENDPOINT: Staging requires the IPv4-compatible Supabase Session Pooler hostname.')
        if parts.get('port','5432')!='5432':
            raise RuntimeError('DB_PORT: Supabase Session Pooler requires port 5432; do not use transaction port 6543.')
        if parts.get('user')!='postgres.inshzjzlcwklaxpxcpve':
            raise RuntimeError('DB_USER: Use the EVAMCARE Session Pooler username from Supabase Connect, not the direct postgres username.')
    return parts

class Row(dict):
    def __getitem__(self,key):
        if isinstance(key,int):return list(self.values())[key]
        return super().__getitem__(key)

class Cursor:
    def __init__(self,cursor):self.cursor=cursor
    @property
    def rowcount(self):return self.cursor.rowcount
    def fetchone(self):
        row=self.cursor.fetchone();return Row(row) if row is not None else None
    def fetchall(self):return [Row(r) for r in self.cursor.fetchall()]
    def __iter__(self):return iter(self.fetchall())

def translate(query):
    # SQL here is application-owned; values always remain separately bound.
    output=[];quoted=False;i=0
    while i<len(query):
        char=query[i]
        if char=="'":
            if quoted and i+1<len(query) and query[i+1]=="'":output.extend([char,char]);i+=2;continue
            quoted=not quoted
        output.append('%s' if char=='?' and not quoted else char)
        i+=1
    value=''.join(output)
    if re.search(r'\bINSERT\s+OR\s+IGNORE\b',value,re.I):
        value=re.sub(r'\bINSERT\s+OR\s+IGNORE\b','INSERT',value,flags=re.I).rstrip().rstrip(';')+' ON CONFLICT DO NOTHING'
    return value

class Connection:
    def __init__(self,url):
        self.schema=os.getenv('DERMASCAN_POSTGRES_SCHEMA','evamcare_local')
        if not re.fullmatch(r'[a-z][a-z0-9_]{0,62}',self.schema):raise ValueError('Invalid PostgreSQL schema')
        # Production requires a valid CA chain. Local CI explicitly opts out for its loopback DB.
        sslmode=os.getenv('DERMASCAN_POSTGRES_SSLMODE','verify-full')
        if os.getenv('DERMASCAN_ENV')=='production' and sslmode!='verify-full':raise ValueError('Production PostgreSQL requires verify-full TLS')
        options={'sslmode':sslmode,'connect_timeout':10,'prepare_threshold':None,'row_factory':dict_row}
        if sslmode=='verify-full':options['sslrootcert']=os.getenv('PGSSLROOTCERT','system')
        try:
            validate_staging_connection(url)
            self.raw=pg_connect(url,**options)
        except RuntimeError:
            raise
        except Exception as error:
            raise RuntimeError(connection_diagnostic(error)) from None
        self.raw.execute(sql.SQL('SET search_path TO {}, pg_catalog').format(sql.Identifier(self.schema)))

    def execute(self,query,params=()):
        if query.strip().upper()=='BEGIN IMMEDIATE':
            # Serialize one-time provisioning/token consumption across backend processes.
            return Cursor(self.raw.execute('LOCK TABLE user_profiles IN EXCLUSIVE MODE'))
        pragma=re.fullmatch(r'\s*PRAGMA table_info\((\w+)\)\s*',query,re.I)
        if pragma:
            return Cursor(self.raw.execute('SELECT column_name AS name FROM information_schema.columns WHERE table_schema=%s AND table_name=%s',(self.schema,pragma.group(1))))
        return Cursor(self.raw.execute(translate(query),params or None))

    def executescript(self,script):
        for statement in script.split(';'):
            if statement.strip():self.execute(statement)

    def executemany(self,query,rows):
        cursor=self.raw.cursor()
        cursor.executemany(translate(query),rows)
        return Cursor(cursor)

    def commit(self):self.raw.commit()
    def rollback(self):self.raw.rollback()
    def close(self):self.raw.close()

    def initialize_schema(self):
        self.raw.execute(sql.SQL('CREATE SCHEMA IF NOT EXISTS {}').format(sql.Identifier(self.schema)))
        self.raw.execute(sql.SQL('REVOKE ALL ON SCHEMA {} FROM PUBLIC').format(sql.Identifier(self.schema)))
        for role in ('anon','authenticated'):
            if self.raw.execute('SELECT 1 FROM pg_roles WHERE rolname=%s',(role,)).fetchone():
                self.raw.execute(sql.SQL('REVOKE ALL ON SCHEMA {} FROM {}').format(sql.Identifier(self.schema),sql.Identifier(role)))

    def secure_tables(self):
        # Fail closed at the Data API boundary. Local Auth authorization stays in FastAPI.
        for row in self.raw.execute('SELECT tablename FROM pg_tables WHERE schemaname=%s',(self.schema,)).fetchall():
            self.raw.execute(sql.SQL('ALTER TABLE {}.{} ENABLE ROW LEVEL SECURITY').format(sql.Identifier(self.schema),sql.Identifier(row['tablename'])))
        self.raw.execute(sql.SQL('REVOKE ALL ON ALL TABLES IN SCHEMA {} FROM PUBLIC').format(sql.Identifier(self.schema)))
        for role in ('anon','authenticated'):
            if self.raw.execute('SELECT 1 FROM pg_roles WHERE rolname=%s',(role,)).fetchone():
                self.raw.execute(sql.SQL('REVOKE ALL ON ALL TABLES IN SCHEMA {} FROM {}').format(sql.Identifier(self.schema),sql.Identifier(role)))
