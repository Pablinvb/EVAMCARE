"""Operator-only completion of an explicit patient erasure request.

No scheduling, blanket purges, credentials or patient data printed. Review legal
retention and backup suppression ledger before invoking against real records.
"""
import argparse
import json
from .database import connect
from .accounts import now

def complete(request_id):
    with connect() as c:
        c.execute('BEGIN IMMEDIATE')
        row=c.execute("SELECT patient_id,status FROM erasure_requests WHERE id=?",(request_id,)).fetchone()
        if not row:raise RuntimeError('Unknown erasure request')
        if row['status']=='completed':return
        pid=row['patient_id']
        patient=c.execute('SELECT session_id FROM patients WHERE id=?',(pid,)).fetchone()
        if not patient:raise RuntimeError('Request requires operator review')
        users=c.execute('SELECT id,status FROM user_profiles WHERE patient_id=?',(pid,)).fetchall()
        if any(u['status']!='inactive' for u in users):raise RuntimeError('Revoke patient access before completing erasure')
        images=c.execute('SELECT i.storage_path FROM scan_images i JOIN skin_scans s ON s.id=i.scan_id WHERE s.patient_id=?',(pid,)).fetchall()
        if images:
            from .private_photos import storage_request, BUCKET
            storage_request('object/'+BUCKET,'DELETE',json.dumps({'prefixes':[r[0] for r in images]}).encode())
        for u in users:
            for table,column in [('account_tokens','user_id'),('user_roles','user_id'),('evaluator_patient_assignments','evaluator_id'),('professional_access_grants','professional_id'),('professional_follow_up_notes','professional_id')]:
                c.execute(f'DELETE FROM {table} WHERE {column}=?',(u['id'],))
            c.execute('DELETE FROM audit_logs WHERE actor_id=?',(u['id'],))
            c.execute('DELETE FROM user_profiles WHERE id=?',(u['id'],))
        c.execute('DELETE FROM scan_images WHERE scan_id IN (SELECT id FROM skin_scans WHERE patient_id=?)',(pid,))
        for table in ('recommendations','shared_records','consents','professional_access_grants','professional_follow_up_notes','evaluator_patient_assignments','audit_logs','patient_datasets','skin_scans'):
            c.execute(f'DELETE FROM {table} WHERE patient_id=?',(pid,))
        c.execute('DELETE FROM appointments WHERE lead_id IN (SELECT id FROM leads WHERE session_id=?)',(patient['session_id'],))
        for table in ('leads','analyses','guidance_assessments'):
            c.execute(f'DELETE FROM {table} WHERE session_id=?',(patient['session_id'],))
        c.execute('DELETE FROM patients WHERE id=?',(pid,))
        c.execute("UPDATE erasure_requests SET status='completed',completed_at=? WHERE id=?",(now(),request_id))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--request-id',required=True);parser.add_argument('--confirm-reviewed',action='store_true',required=True)
    args=parser.parse_args();complete(args.request_id)
