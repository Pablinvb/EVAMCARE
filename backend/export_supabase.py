"""Offline export from a BACKUP: no passwords, session IDs, tokens or demo data."""
import argparse
import json
import os
import sqlite3
from contextlib import closing
from pathlib import Path

TABLES = ['patients','user_profiles','user_roles','evaluator_patient_assignments','skin_scans','scan_images','recommendations','professional_access_grants','professional_follow_up_notes','consents','audit_logs']
EXCLUDED = {'session_id','password_hash','salt'}

def literal(column,value):
    if value is None:return 'NULL'
    if column in {'demo','granted'}:return 'true' if value else 'false'
    if isinstance(value,(int,float)):return str(value)
    escaped=str(value).replace("'","''")
    return "'"+escaped+"'"+('::jsonb' if column.endswith('_json') else '')

def export(source,destination):
    if not source.is_file():raise ValueError('Backup not found')
    with closing(sqlite3.connect(source.resolve().as_uri()+'?mode=ro',uri=True)) as c:
        c.row_factory=sqlite3.Row
        patients={r[0] for r in c.execute('SELECT id FROM patients WHERE demo=0')}
        profiles={r[0] for r in c.execute('SELECT id FROM user_profiles WHERE patient_id IS NULL OR patient_id IN (SELECT id FROM patients WHERE demo=0)')}
        scans={r[0] for r in c.execute('SELECT id FROM skin_scans WHERE patient_id IN (SELECT id FROM patients WHERE demo=0)')}
        fd=os.open(destination,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        with os.fdopen(fd,'w',encoding='utf-8') as output:
            output.write("-- Sensitive patient data. Import only into an empty evamcare schema.\nBEGIN;\nSET standard_conforming_strings=on;\n")
            for table in TABLES:
                for row in c.execute('SELECT * FROM '+table):
                    row=dict(row)
                    if table=='patients' and row['id'] not in patients:continue
                    if table=='user_profiles' and row['id'] not in profiles:continue
                    if row.get('patient_id') and row['patient_id'] not in patients:continue
                    if row.get('scan_id') and row['scan_id'] not in scans:continue
                    if row.get('user_id') and row['user_id'] not in profiles:continue
                    if row.get('professional_id') and row['professional_id'] not in profiles:continue
                    if row.get('evaluator_id') and row['evaluator_id'] not in profiles:continue
                    keys=[k for k in row if k not in EXCLUDED]
                    output.write('INSERT INTO evamcare.'+table+' ('+','.join(keys)+') VALUES ('+','.join(literal(k,row[k]) for k in keys)+');\n')
            output.write('COMMIT;\n')

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',required=True,type=Path)
    parser.add_argument('--destination',required=True,type=Path)
    args=parser.parse_args();export(args.source,args.destination)
    print('Export complete. Auth accounts require invitations and explicit ID mapping. Protect the export.')
