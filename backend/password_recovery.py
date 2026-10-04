"""Email-only password recovery. No plaintext token in API responses or logs."""
import os
import secrets
import smtplib
import ssl
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from .accounts import audit, digest, now, password_hash, throttle_login
from .database import connect

router = APIRouter(prefix='/api/v1/accounts', tags=['Accounts'])

class RecoveryRequest(BaseModel):
    email: str = Field(min_length=5,max_length=254,pattern=r'^[^\s@]+@[^\s@]+\.[^\s@]+$')

class ResetRequest(BaseModel):
    token: str = Field(min_length=20,max_length=200)
    password: str = Field(min_length=12,max_length=256)

def send_recovery_email(recipient, token):
    url = os.environ['DERMASCAN_RECOVERY_URL']
    message = EmailMessage()
    message['From'] = os.environ['DERMASCAN_SMTP_FROM']
    message['To'] = recipient
    message['Subject'] = 'EVAMCARE: recuperación de contraseña'
    message.set_content('Para cambiar tu contraseña abre este enlace. Vence en 30 minutos.\n'
                        + url + '#reset=' + token + '\nSi no lo solicitaste, ignora este correo.')
    host = os.environ['DERMASCAN_SMTP_HOST']
    port = int(os.getenv('DERMASCAN_SMTP_PORT','587'))
    with smtplib.SMTP(host, port, timeout=10) as smtp:
        smtp.ehlo()
        smtp.starttls(context=ssl.create_default_context())
        smtp.ehlo()
        smtp.login(os.environ['DERMASCAN_SMTP_USER'],os.environ['DERMASCAN_SMTP_PASSWORD'])
        smtp.send_message(message)

@router.post('/password-recovery')
def recover(body: RecoveryRequest, request: Request):
    throttle_login(request,'recovery:'+body.email)
    keys=['DERMASCAN_SMTP_HOST','DERMASCAN_SMTP_FROM','DERMASCAN_SMTP_USER','DERMASCAN_SMTP_PASSWORD','DERMASCAN_RECOVERY_URL']
    if not all(os.getenv(k) for k in keys):
        raise HTTPException(503,'Recuperación por correo pendiente de configurar')
    url=urlsplit(os.environ['DERMASCAN_RECOVERY_URL'])
    if url.scheme!='https' or not url.netloc or url.fragment or url.query:
        raise HTTPException(503,'Recuperación por correo pendiente de configurar')
    token=secrets.token_urlsafe(32)
    uid=None
    with connect() as c:
        row=c.execute("SELECT id,email FROM user_profiles WHERE email=? AND status='active'",(body.email.strip().lower(),)).fetchone()
        if row:
            uid=row['id']
            c.execute("DELETE FROM account_tokens WHERE user_id=? AND kind='reset'",(uid,))
            c.execute('INSERT INTO account_tokens VALUES(?,?,?,?)',(digest(token),uid,'reset',(datetime.now(timezone.utc)+timedelta(minutes=30)).isoformat()))
    if uid:
        try:
            send_recovery_email(row['email'],token)
        except Exception:
            # No SMTP diagnostics: providers can include credentials or the email body.
            with connect() as c: c.execute('DELETE FROM account_tokens WHERE hash=?',(digest(token),))
    return {'ok':True,'message':'Si la cuenta está activa, recibirás instrucciones por correo.'}

@router.post('/password-reset')
def reset(body: ResetRequest,request: Request):
    throttle_login(request,'reset:'+digest(body.token))
    salt=secrets.token_hex(16)
    hashed=password_hash(body.password,salt)
    with connect() as c:
        c.execute('BEGIN IMMEDIATE')
        row=c.execute("SELECT t.user_id FROM account_tokens t JOIN user_profiles u ON u.id=t.user_id WHERE t.hash=? AND t.kind='reset' AND t.expires_at>? AND u.status='active'",(digest(body.token),now())).fetchone()
        if not row: raise HTTPException(400,'Enlace inválido o vencido')
        c.execute('UPDATE user_profiles SET password_hash=?,salt=? WHERE id=?',(hashed,salt,row['user_id']))
        c.execute('DELETE FROM account_tokens WHERE user_id=?',(row['user_id'],))
        audit(c,row['user_id'],'PASSWORD_RESET',row['user_id'])
    return {'ok':True,'message':'Contraseña actualizada. Inicia sesión de nuevo.'}
