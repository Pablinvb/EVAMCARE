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
            self.raw=pg_connect(url,**options)
        except Exception:
            raise RuntimeError('PostgreSQL connection failed. Check secure database configuration.') from None
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
