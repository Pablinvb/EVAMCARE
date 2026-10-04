"""Opt-in fictional staging accounts. Passwords only come from private env vars."""
import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from .accounts import now, password_hash
from .database import connect

def seed():
    if os.getenv('DERMASCAN_STAGING_DEMO')!='true':return
    if os.getenv('DERMASCAN_POSTGRES_SCHEMA')!='evamcare_staging' or not os.getenv('DATABASE_URL'):
        raise RuntimeError('Demo provisioning is restricted to isolated PostgreSQL staging.')
    roles=('evaluator','patient','professional')
    passwords={role:os.getenv('DERMASCAN_DEMO_'+role.upper()+'_PASSWORD','') for role in roles}
    if any(not 12<=len(value)<=256 for value in passwords.values()):
        raise RuntimeError('Configure all three demo password secrets (12–256 characters).')
    with connect() as c:
        c.execute('BEGIN IMMEDIATE')
        ids={};patient_id=None
        for role in roles:
            email=role+'@evamcare.example.test'
            existing=c.execute('SELECT id,patient_id FROM user_profiles WHERE email=?',(email,)).fetchone()
            if existing:
                ids[role]=existing['id']
                if role=='patient':patient_id=existing['patient_id']
                continue
            uid=str(uuid4());ids[role]=uid;pid=None
            if role=='patient':
                pid=patient_id=str(uuid4())
                c.execute("INSERT INTO patients(id,patient_code,session_id,first_name,email,skin_goals_json,demo,created_at,updated_at) VALUES(?,?,?,?,?,'[]',0,?,?)",(pid,'DS-'+secrets.token_hex(4).upper(),secrets.token_hex(32),'Paciente ficticio de staging',email,now(),now()))
            salt=secrets.token_hex(16)
            c.execute('INSERT INTO user_profiles VALUES(?,?,?,?,?,?,?,?,?)',(uid,email,'Demo '+role,'active',password_hash(passwords[role],salt),salt,pid,'Dermatología (demo)' if role=='professional' else None,now()))
            c.execute('INSERT INTO user_roles VALUES(?,?)',(uid,role))
        c.execute('INSERT OR IGNORE INTO evaluator_patient_assignments VALUES(?,?)',(ids['evaluator'],patient_id))
        if not c.execute('SELECT 1 FROM professional_access_grants WHERE patient_id=? AND professional_id=?',(patient_id,ids['professional'])).fetchone():
            c.execute('INSERT INTO professional_access_grants VALUES(?,?,?,?,?,NULL)',(str(uuid4()),patient_id,ids['professional'],json.dumps(['profile','scans','evolution','recommendations']),(datetime.now(timezone.utc)+timedelta(hours=24)).isoformat()))
