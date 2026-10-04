"""Run on the live instance BEFORE redeploy. Never replaces a destination."""
import argparse
import os
import sqlite3
from contextlib import closing
from pathlib import Path

def backup(source: Path, destination: Path):
    source=source.resolve(); destination=destination.resolve()
    if source==destination or not source.is_file(): raise ValueError('Invalid source or destination')
    # Exclusive creation prevents accidentally overwriting a backup or a live DB.
    descriptor=os.open(destination,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    os.close(descriptor)
    try:
        with closing(sqlite3.connect(source.as_uri()+'?mode=ro',uri=True)) as src, closing(sqlite3.connect(destination)) as dst:
            src.backup(dst)
            if dst.execute('PRAGMA integrity_check').fetchone()[0]!='ok': raise ValueError('Backup integrity check failed')
    except Exception:
        # Keep the failed artifact for inspection; do not delete or overwrite anything.
        raise

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',required=True,type=Path)
    parser.add_argument('--destination',required=True,type=Path)
    args=parser.parse_args()
    backup(args.source,args.destination)
    print('Backup completed and integrity verified. Protect this file as patient data.')
