"""Local account provider. Tokens are opaque and only hashes are persisted."""
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from .database import connect

router = APIRouter(prefix="/api/v1/accounts", tags=["Accounts"])
ROLES = {"admin", "evaluator", "patient", "professional"}
login_attempts = defaultdict(deque)
login_lock = threading.Lock()

def throttle_login(request, email):
    with login_lock:
        timestamp=time.monotonic()
        for key,limit in [('ip:'+(request.client.host if request.client else 'unknown'),30),('email:'+email.strip().lower(),10)]:
            bucket=login_attempts[key]
            while bucket and bucket[0]<timestamp-600: bucket.popleft()
            if len(bucket)>=limit: raise HTTPException(429,'Demasiados intentos. Intenta más tarde.')
            bucket.append(timestamp)

def now():
    return datetime.now(timezone.utc).isoformat()

def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()

def password_hash(password, salt):
    value = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=32768, r=8, p=1, maxmem=128*1024*1024).hex()
    return 'scrypt-v2$' + value

def password_matches(password, salt, stored):
    if stored.startswith('scrypt-v2$'):
        candidate = password_hash(password, salt)
    else:
        # Preserve access for accounts created before versioned hashes.
        candidate = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
    return hmac.compare_digest(candidate, stored)

def initialize_accounts():
    with connect() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS user_profiles(id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, name TEXT NOT NULL, status TEXT NOT NULL, password_hash TEXT, salt TEXT, patient_id TEXT UNIQUE, specialty TEXT, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS user_roles(user_id TEXT NOT NULL REFERENCES user_profiles(id), role TEXT NOT NULL CHECK(role IN ('admin','evaluator','patient','professional')), PRIMARY KEY(user_id,role));
        CREATE TABLE IF NOT EXISTS account_tokens(hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES user_profiles(id), kind TEXT NOT NULL, expires_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS evaluator_patient_assignments(evaluator_id TEXT NOT NULL REFERENCES user_profiles(id), patient_id TEXT NOT NULL REFERENCES patients(id), PRIMARY KEY(evaluator_id,patient_id));
        CREATE TABLE IF NOT EXISTS professional_access_grants(id TEXT PRIMARY KEY, patient_id TEXT NOT NULL REFERENCES patients(id), professional_id TEXT NOT NULL REFERENCES user_profiles(id), scopes_json TEXT NOT NULL, expires_at TEXT NOT NULL, revoked_at TEXT);
        CREATE TABLE IF NOT EXISTS professional_follow_up_notes(id TEXT PRIMARY KEY, patient_id TEXT NOT NULL REFERENCES patients(id), professional_id TEXT NOT NULL REFERENCES user_profiles(id), body TEXT NOT NULL, created_at TEXT NOT NULL);
        ''')
        email = os.getenv("DERMASCAN_BOOTSTRAP_ADMIN_EMAIL")
        password = os.getenv("DERMASCAN_BOOTSTRAP_ADMIN_PASSWORD")
        c.execute('BEGIN IMMEDIATE')
        if email and password and 12 <= len(password) <= 256 and not c.execute("SELECT 1 FROM user_profiles").fetchone():
            uid, salt = str(uuid4()), secrets.token_hex(16)
            c.execute("INSERT INTO user_profiles VALUES(?,?,?,?,?,?,?,?,?)", (uid,email.strip().lower(),"Administrador","active",password_hash(password,salt),salt,None,None,now()))
            c.execute("INSERT INTO user_roles VALUES(?, 'admin')", (uid,))
            audit(c,uid,'ADMIN_BOOTSTRAPPED',uid)

def audit(c, actor, action, resource):
    c.execute("INSERT INTO audit_logs VALUES(?,?,?,?,?,?,?,?)", (str(uuid4()),None,actor,action,"account",resource,now(),"{}"))

def current_user(authorization: str | None = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401,"Inicia sesión")
    with connect() as c:
        row = c.execute("SELECT u.* FROM user_profiles u JOIN account_tokens t ON u.id=t.user_id WHERE t.hash=? AND t.kind='session' AND t.expires_at>? AND u.status='active'", (digest(authorization[7:]),now())).fetchone()
        if not row: raise HTTPException(401,"Sesión vencida o cuenta inactiva")
        user = dict(row)
        user['roles'] = [r[0] for r in c.execute("SELECT role FROM user_roles WHERE user_id=?",(user['id'],))]
        return user

def require(user, *roles):
    if not set(user['roles']).intersection(roles): raise HTTPException(403,"Acceso no autorizado")

def public(user):
    return {k:v for k,v in user.items() if k not in {'password_hash','salt'}}

class Login(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(min_length=12,max_length=256)

class Invite(BaseModel):
    email: str = Field(min_length=5,max_length=254,pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    name: str = Field(min_length=2,max_length=120)
    roles: list[str] = Field(min_length=1,max_length=4)
    specialty: str | None = Field(default=None,max_length=120)

class Activate(BaseModel):
    token: str
    password: str = Field(min_length=12,max_length=256)

@router.post('/login')
def login(body: Login,request: Request):
    throttle_login(request,body.email)
    with connect() as c:
        u = c.execute("SELECT * FROM user_profiles WHERE email=? AND status='active'",(body.email.strip().lower(),)).fetchone()
        if not u or not u['salt'] or not password_matches(body.password,u['salt'],u['password_hash']): raise HTTPException(401,"Credenciales inválidas")
        token = secrets.token_urlsafe(32)
        c.execute("INSERT INTO account_tokens VALUES(?,?,?,?)",(digest(token),u['id'],'session',(datetime.now(timezone.utc)+timedelta(hours=8)).isoformat()))
        return {'token':token}

@router.get('/me')
def me(user=Depends(current_user)): return public(user)

@router.post('/logout')
def logout(user=Depends(current_user), authorization: str = Header()):
    with connect() as c: c.execute("DELETE FROM account_tokens WHERE hash=?",(digest(authorization[7:]),))
    return {'ok':True}

@router.get('/patients')
def directory(q: str = '', user=Depends(current_user)):
    require(user,'admin','evaluator')
    with connect() as c:
        rows=c.execute("SELECT p.id,p.patient_code,p.first_name,p.email,MAX(s.scan_date) last_evaluation,COUNT(s.id) scan_count FROM patients p LEFT JOIN skin_scans s ON s.patient_id=p.id WHERE p.demo=0 AND (p.first_name LIKE ? OR p.email LIKE ? OR p.patient_code LIKE ?) AND (?=1 OR EXISTS(SELECT 1 FROM evaluator_patient_assignments a WHERE a.patient_id=p.id AND a.evaluator_id=?)) GROUP BY p.id",('%'+q+'%',)*3+(int('admin' in user['roles']),user['id'])).fetchall()
        return {'items':[dict(r) for r in rows]}

class Assignment(BaseModel):
    evaluatorId: str
    patientId: str

@router.post('/assignments')
def assign(body: Assignment,user=Depends(current_user)):
    require(user,'admin')
    with connect() as c:
        if not c.execute("SELECT 1 FROM user_roles r JOIN user_profiles u ON u.id=r.user_id WHERE r.user_id=? AND r.role='evaluator' AND u.status='active'",(body.evaluatorId,)).fetchone() or not c.execute('SELECT 1 FROM patients WHERE id=? AND demo=0',(body.patientId,)).fetchone(): raise HTTPException(400,'Paciente o evaluador inválido')
        c.execute('INSERT OR IGNORE INTO evaluator_patient_assignments VALUES(?,?)',(body.evaluatorId,body.patientId))
        audit(c,user['id'],'PATIENT_ASSIGNED',body.patientId)
    return {'ok':True}

@router.get('/professionals')
def professionals(q: str = '',user=Depends(current_user)):
    require(user,'patient')
    with connect() as c:
        return {'items':[dict(r) for r in c.execute("SELECT u.id,u.name,u.specialty FROM user_profiles u JOIN user_roles r ON u.id=r.user_id WHERE r.role='professional' AND u.status='active' AND u.name LIKE ?",('%'+q+'%',))]}

class Grant(BaseModel):
    professionalId: str
    scopes: list[str] = Field(min_length=1,max_length=5)
    hours: int = Field(default=72,ge=1,le=720)

@router.post('/grants',status_code=201)
def grant(body: Grant,user=Depends(current_user)):
    require(user,'patient')
    if not user['patient_id'] or not set(body.scopes)<={'profile','scans','photographs','evolution','recommendations'}: raise HTTPException(400,'Permisos inválidos')
    gid=str(uuid4())
    with connect() as c:
        if not c.execute("SELECT 1 FROM user_profiles u JOIN user_roles r ON u.id=r.user_id WHERE u.id=? AND u.status='active' AND r.role='professional'",(body.professionalId,)).fetchone(): raise HTTPException(400,'Profesional no disponible')
        c.execute('INSERT INTO professional_access_grants VALUES(?,?,?,?,?,NULL)',(gid,user['patient_id'],body.professionalId,json.dumps(body.scopes),(datetime.now(timezone.utc)+timedelta(hours=body.hours)).isoformat()))
        audit(c,user['id'],'RECORD_SHARED',gid)
    return {'id':gid}

@router.get('/grants')
def grants(user=Depends(current_user)):
    require(user,'patient','professional')
    with connect() as c:
        return {'items':[dict(r) for r in c.execute('SELECT g.*,p.first_name,p.patient_code,u.name professional_name FROM professional_access_grants g JOIN patients p ON p.id=g.patient_id JOIN user_profiles u ON u.id=g.professional_id WHERE g.patient_id=? OR g.professional_id=?',(user['patient_id'],user['id']))]}

@router.post('/grants/{gid}/revoke')
def revoke(gid: str,user=Depends(current_user)):
    require(user,'patient')
    with connect() as c:
        if not c.execute('UPDATE professional_access_grants SET revoked_at=? WHERE id=? AND patient_id=?',(now(),gid,user['patient_id'])).rowcount: raise HTTPException(404,'Permiso no encontrado')
        audit(c,user['id'],'SHARE_REVOKED',gid)
    return {'ok':True}

def record_session(user,pid):
    with connect() as c:
        patient=c.execute('SELECT * FROM patients WHERE id=? AND demo=0',(pid,)).fetchone()
        if not patient: raise HTTPException(404,'Paciente no encontrado')
        if not (user['patient_id']==pid and 'patient' in user['roles']) and not ('evaluator' in user['roles'] and c.execute('SELECT 1 FROM evaluator_patient_assignments WHERE evaluator_id=? AND patient_id=?',(user['id'],pid)).fetchone()): raise HTTPException(403,'Expediente no autorizado')
        return patient['session_id']

@router.get('/patients/{pid}/record')
def record(pid: str,user=Depends(current_user)):
    from .patient_platform import get_dashboard,get_timeline,list_recommendations
    scopes={'profile','scans','evolution','recommendations'}
    try: session=record_session(user,pid)
    except HTTPException as e:
        if e.status_code!=403 or 'professional' not in user['roles']: raise
        with connect() as c:
            rows=c.execute('SELECT scopes_json FROM professional_access_grants WHERE patient_id=? AND professional_id=? AND revoked_at IS NULL AND expires_at>?',(pid,user['id'],now())).fetchall()
            if not rows: raise HTTPException(403,'Permiso vencido, revocado o inexistente')
            scopes=set().union(*(set(json.loads(r[0])) for r in rows))
            session=c.execute('SELECT session_id FROM patients WHERE id=?',(pid,)).fetchone()[0]
    result={}
    dashboard=get_dashboard(session)
    if 'profile' in scopes: result['patient']=dashboard['patient']
    if 'scans' in scopes:
        from .patient_platform import list_patient_scans
        result['scans']=list_patient_scans(session,100)
    if 'evolution' in scopes: result['evolution']=get_timeline(session)
    if 'recommendations' in scopes: result['recommendations']=list_recommendations(session)
    with connect() as c: audit(c,user['id'],'RECORD_ACCESSED',pid)
    return result

class Note(BaseModel):
    body: str = Field(min_length=1,max_length=10000)

@router.post('/patients/{pid}/notes',status_code=201)
def note(pid: str,body: Note,user=Depends(current_user)):
    require(user,'professional')
    with connect() as c:
        if not c.execute('SELECT 1 FROM professional_access_grants WHERE patient_id=? AND professional_id=? AND revoked_at IS NULL AND expires_at>?',(pid,user['id'],now())).fetchone(): raise HTTPException(403,'Expediente no autorizado')
        nid=str(uuid4()); c.execute('INSERT INTO professional_follow_up_notes VALUES(?,?,?,?,?)',(nid,pid,user['id'],body.body,now()))
        audit(c,user['id'],'FOLLOW_UP_CREATED',nid)
    return {'id':nid}

@router.get('/patients/{pid}/notes')
def notes(pid: str,user=Depends(current_user)):
    require(user,'professional')
    record(pid,user)
    with connect() as c: return {'items':[dict(r) for r in c.execute('SELECT * FROM professional_follow_up_notes WHERE patient_id=? AND professional_id=?',(pid,user['id']))]}

@router.get('/users')
def users(q: str = '', role: str = '', status: str = '', user=Depends(current_user)):
    require(user,'admin')
    with connect() as c:
        rows = c.execute("SELECT DISTINCT u.*,p.patient_code FROM user_profiles u LEFT JOIN patients p ON p.id=u.patient_id LEFT JOIN user_roles r ON r.user_id=u.id WHERE (u.name LIKE ? OR u.email LIKE ? OR p.patient_code LIKE ?) AND (?='' OR r.role=?) AND (?='' OR u.status=?)",('%'+q+'%',)*3+(role,role,status,status)).fetchall()
        result=[]
        for row in rows:
            item=public(dict(row)); item['roles']=[r[0] for r in c.execute('SELECT role FROM user_roles WHERE user_id=?',(row['id'],))]; result.append(item)
        return {'items':result}

@router.post('/invite',status_code=201)
def invite(body: Invite,user=Depends(current_user)):
    require(user,'admin','evaluator')
    if not set(body.roles)<=ROLES or ('admin' not in user['roles'] and body.roles!=['patient']): raise HTTPException(403,'Roles no autorizados')
    uid, token = str(uuid4()),secrets.token_urlsafe(32)
    with connect() as c:
        if c.execute('SELECT 1 FROM user_profiles WHERE email=?',(body.email.strip().lower(),)).fetchone(): raise HTTPException(409,'Ya existe una cuenta con este correo')
        pid=None
        if 'patient' in body.roles:
            pid=str(uuid4())
            c.execute("INSERT INTO patients(id,patient_code,session_id,first_name,email,skin_goals_json,demo,created_at,updated_at) VALUES(?,?,?,?,?,'[]',0,?,?)",(pid,'DS-'+secrets.token_hex(4).upper(),secrets.token_hex(32),body.name,body.email.strip().lower(),now(),now()))
            if 'evaluator' in user['roles']: c.execute('INSERT INTO evaluator_patient_assignments VALUES(?,?)',(user['id'],pid))
        c.execute('INSERT INTO user_profiles VALUES(?,?,?,?,?,?,?,?,?)',(uid,body.email.strip().lower(),body.name,'pending',None,None,pid,body.specialty,now()))
        for role in set(body.roles): c.execute('INSERT INTO user_roles VALUES(?,?)',(uid,role))
        c.execute('INSERT INTO account_tokens VALUES(?,?,?,?)',(digest(token),uid,'invite',(datetime.now(timezone.utc)+timedelta(hours=48)).isoformat()))
        audit(c,user['id'],'ACCOUNT_INVITED',uid)
    return {'id':uid,'activationToken':token,'patientId':pid}

@router.post('/activate')
def activate(body: Activate):
    with connect() as c:
        c.execute('BEGIN IMMEDIATE')
        token=c.execute("SELECT * FROM account_tokens WHERE hash=? AND kind='invite' AND expires_at>?",(digest(body.token),now())).fetchone()
        if not token: raise HTTPException(400,'Invitación inválida o vencida')
        salt=secrets.token_hex(16)
        c.execute("UPDATE user_profiles SET password_hash=?,salt=?,status='active' WHERE id=? AND status='pending'",(password_hash(body.password,salt),salt,token['user_id']))
        c.execute('DELETE FROM account_tokens WHERE hash=?',(digest(body.token),))
    return {'ok':True}

class Update(BaseModel):
    name: str = Field(min_length=2,max_length=120)
    status: str = Field(pattern='^(active|inactive|pending)$')
    roles: list[str] = Field(min_length=1,max_length=4)

@router.put('/users/{uid}')
def update(uid: str,body: Update,user=Depends(current_user)):
    require(user,'admin')
    if not set(body.roles)<=ROLES or uid==user['id']: raise HTTPException(400,'Cambio no permitido')
    with connect() as c:
        target=c.execute('SELECT * FROM user_profiles WHERE id=?',(uid,)).fetchone()
        if not target: raise HTTPException(404,'Cuenta no encontrada')
        if body.status=='active' and not target['password_hash']: raise HTTPException(400,'Activa la cuenta mediante invitación')
        c.execute('UPDATE user_profiles SET name=?,status=? WHERE id=?',(body.name,body.status,uid))
        c.execute('DELETE FROM user_roles WHERE user_id=?',(uid,))
        for role in set(body.roles): c.execute('INSERT INTO user_roles VALUES(?,?)',(uid,role))
        audit(c,user['id'],'ACCOUNT_UPDATED',uid)
    return {'ok':True}
