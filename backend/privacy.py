"""Pilot privacy controls. Not a declaration of legal compliance."""
import os
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from .accounts import current_user, require, now, password_matches
from .database import connect
VERSION='2026-10-pilot-1'
router=APIRouter(prefix='/api/v1/privacy',tags=['Privacy'])

def initialize():
    with connect() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS patient_datasets(patient_id TEXT PRIMARY KEY REFERENCES patients(id), dataset TEXT NOT NULL CHECK(dataset IN ('test','real','unclassified')));
        CREATE TABLE IF NOT EXISTS erasure_requests(id TEXT PRIMARY KEY, patient_id TEXT NOT NULL UNIQUE, requested_at TEXT NOT NULL, status TEXT NOT NULL, completed_at TEXT);
        ''')

def register_dataset(c,pid,dataset):
    if dataset=='real':
        if os.getenv('DERMASCAN_POSTGRES_SCHEMA')=='evamcare_staging' or os.getenv('DERMASCAN_REAL_PATIENTS_ENABLED')!='true':raise HTTPException(403,'Este entorno admite únicamente pacientes ficticios')
        if not all(os.getenv(k) for k in ('DERMASCAN_PRIVACY_CONTROLLER','DERMASCAN_PRIVACY_CONTACT','DERMASCAN_RETENTION_POLICY')):raise HTTPException(503,'Configura responsable, contacto de privacidad y conservación antes del piloto real')
    c.execute('INSERT INTO patient_datasets VALUES(?,?)',(pid,dataset))

@router.get('/notice')
def notice():
    return {'version':VERSION,'controller':os.getenv('DERMASCAN_PRIVACY_CONTROLLER'),'contact':os.getenv('DERMASCAN_PRIVACY_CONTACT'),'retention':os.getenv('DERMASCAN_RETENTION_POLICY'),
      'purpose':'Evaluación cosmética orientativa e historial; no diagnóstico ni validación médica.',
      'data':'Perfil, cuestionario y resultados. La fotografía se procesa sin guardarla; adjuntarla requiere consentimiento separado.',
      'processors':['Render (hosting)','Supabase (PostgreSQL y almacenamiento opcional)'],
      'rights':'Acceso, rectificación, retiro del consentimiento y solicitud de eliminación. Compartir con profesionales es opcional y revocable.',
      'limitations':'Piloto limitado a adultos; no decisiones médicas ni atención de emergencias.',
      'backups':'La eliminación en copias depende de la conservación configurada; una restauración debe reaplicar solicitudes de eliminación.'}

class Consent(BaseModel):
    purpose: str=Field(pattern='^(evaluation|photo_storage)$')
    granted: bool
    version: str

@router.post('/consent')
def consent(body: Consent,user=Depends(current_user)):
    require(user,'patient')
    if not user['patient_id'] or body.version!=VERSION:raise HTTPException(400,'Revisa la versión actual del aviso')
    with connect() as c:
        c.execute('UPDATE consents SET revoked_at=? WHERE patient_id=? AND consent_type=? AND revoked_at IS NULL',(now(),user['patient_id'],body.purpose))
        c.execute('INSERT INTO consents VALUES(?,?,?,?,?,?,?)',(str(uuid4()),user['patient_id'],body.purpose,int(body.granted),now() if body.granted else None,None,VERSION))
    return {'ok':True}

@router.get('/export')
def export(user=Depends(current_user)):
    require(user,'patient')
    from .accounts import record
    return {'noticeVersion':VERSION,'record':record(user['patient_id'],user)}

class Erasure(BaseModel):
    password: str=Field(min_length=12,max_length=256)
    confirmation: str=Field(pattern='^SOLICITAR ELIMINACIÓN$')

@router.post('/erasure',status_code=202)
def erasure(body: Erasure,user=Depends(current_user)):
    require(user,'patient')
    if set(user['roles'])!={'patient'}:raise HTTPException(409,'Una cuenta con funciones adicionales requiere revisión individual de eliminación')
    if not user['patient_id']:raise HTTPException(400,'No existe expediente asociado')
    if not password_matches(body.password,user['salt'],user['password_hash']):raise HTTPException(401,'Confirma tu contraseña')
    with connect() as c:
        c.execute('BEGIN IMMEDIATE')
        c.execute('INSERT OR IGNORE INTO erasure_requests VALUES(?,?,?,?,NULL)',(str(uuid4()),user['patient_id'],now(),'pending'))
        c.execute('UPDATE professional_access_grants SET revoked_at=? WHERE patient_id=?',(now(),user['patient_id']))
        c.execute('UPDATE shared_records SET revoked_at=? WHERE patient_id=?',(now(),user['patient_id']))
        c.execute('DELETE FROM evaluator_patient_assignments WHERE patient_id=?',(user['patient_id'],))
        c.execute('DELETE FROM account_tokens WHERE user_id=?',(user['id'],))
        c.execute("UPDATE user_profiles SET status='inactive' WHERE id=?",(user['id'],))
    return {'status':'pending','message':'Solicitud recibida. Accesos revocados; la supresión física está pendiente, no terminada.'}
