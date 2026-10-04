"""Optional private Storage via backend proxy; local Auth remains the only login.

No public URLs or persistent signed URLs. Authorization is checked at each read.
"""
import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request as HTTPRequest, urlopen
from uuid import uuid4

import cv2
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from fastapi.concurrency import run_in_threadpool
from .accounts import current_user, now, record_session
from .database import connect

router=APIRouter(prefix='/api/v1/accounts',tags=['Private photographs'])
BUCKET='evamcare-photos'

def storage_request(path,method='GET',body=None,content_type='application/json'):
    base=os.getenv('SUPABASE_URL','').rstrip('/')
    key=os.getenv('SUPABASE_SERVICE_ROLE_KEY')
    if urlsplit(base).scheme!='https' or not key:raise HTTPException(503,'Almacenamiento privado pendiente de configurar')
    request=HTTPRequest(base+'/storage/v1/'+path,data=body,method=method,headers={'apikey':key,'Authorization':'Bearer '+key,'Content-Type':content_type})
    try:
        with urlopen(request,timeout=15) as response:return response.read()
    except HTTPError as error:
        if error.code==404:raise HTTPException(404,'Recurso privado no encontrado') from None
        raise HTTPException(503,'Almacenamiento privado no disponible') from None
    except URLError:
        raise HTTPException(503,'Almacenamiento privado no disponible') from None

def ensure_bucket():
    try:
        bucket=json.loads(storage_request('bucket/'+BUCKET))
        if bucket.get('public') is not False:raise HTTPException(503,'El bucket debe ser privado')
    except HTTPException as error:
        if error.status_code!=404:raise
        storage_request('bucket','POST',json.dumps({'id':BUCKET,'name':BUCKET,'public':False,'file_size_limit':10485760,'allowed_mime_types':['image/jpeg','image/png','image/webp']}).encode())

def photo_permission(user,pid):
    try:
        record_session(user,pid)
        return
    except HTTPException as error:
        if error.status_code!=403:raise
    if 'professional' not in user['roles']:raise HTTPException(403,'Fotografías no autorizadas')
    with connect() as c:
        rows=c.execute('SELECT scopes_json FROM professional_access_grants WHERE patient_id=? AND professional_id=? AND revoked_at IS NULL AND expires_at>?',(pid,user['id'],now())).fetchall()
    if not any('photographs' in json.loads(r[0]) for r in rows):raise HTTPException(403,'Fotografías no autorizadas')

@router.post('/patients/{pid}/scans/{sid}/photo',status_code=201)
async def upload(pid: str,sid: str,image: UploadFile=File(),consent: bool=Form(False),user=Depends(current_user)):
    record_session(user,pid)
    if not consent:raise HTTPException(400,'El almacenamiento de fotografías requiere consentimiento explícito')
    with connect() as c:
        if not c.execute('SELECT 1 FROM skin_scans WHERE id=? AND patient_id=?',(sid,pid)).fetchone():raise HTTPException(404,'Evaluación no encontrada')
    from .main import decode_upload
    decoded=await decode_upload(image)
    ok,encoded=cv2.imencode('.jpg',decoded)
    if not ok or len(encoded)>10485760:raise HTTPException(400,'Fotografía no válida')
    await run_in_threadpool(ensure_bucket)
    identifier=str(uuid4());path=f'{pid}/{sid}/{identifier}.jpg'
    await run_in_threadpool(storage_request,'object/'+BUCKET+'/'+quote(path,safe='/'),'POST',encoded.tobytes(),'image/jpeg')
    with connect() as c:
        c.execute('INSERT INTO scan_images VALUES(?,?,?,?,?)',(identifier,sid,'face',path,now()))
        c.execute('INSERT INTO consents(id,patient_id,consent_type,granted,granted_at,version) VALUES(?,?,?,?,?,?)',(str(uuid4()),pid,'photo_storage',1,now(),'1'))
        c.execute('INSERT INTO audit_logs VALUES(?,?,?,?,?,?,?,?)',(str(uuid4()),pid,user['id'],'PHOTO_STORED','scan_image',identifier,now(),'{}'))
    return {'id':identifier,'private':True}

@router.get('/patients/{pid}/photos')
def photos(pid: str,user=Depends(current_user)):
    photo_permission(user,pid)
    with connect() as c:
        rows=c.execute('SELECT i.id,i.scan_id,i.image_type,i.created_at FROM scan_images i JOIN skin_scans s ON s.id=i.scan_id WHERE s.patient_id=? ORDER BY i.created_at DESC',(pid,)).fetchall()
    return {'items':[dict(r) for r in rows]}

@router.get('/patients/{pid}/photos/{image_id}')
def download(pid: str,image_id: str,user=Depends(current_user)):
    photo_permission(user,pid)
    with connect() as c:
        row=c.execute('SELECT i.storage_path FROM scan_images i JOIN skin_scans s ON s.id=i.scan_id WHERE i.id=? AND s.patient_id=?',(image_id,pid)).fetchone()
        if not row:raise HTTPException(404,'Fotografía no encontrada')
        c.execute('INSERT INTO audit_logs VALUES(?,?,?,?,?,?,?,?)',(str(uuid4()),pid,user['id'],'PHOTO_ACCESSED','scan_image',image_id,now(),'{}'))
    contents=storage_request('object/'+BUCKET+'/'+quote(row[0],safe='/'))
    return Response(contents,media_type='image/jpeg',headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})
