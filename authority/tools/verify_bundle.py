"""Verify every bundled hash and optionally extract into a new directory."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

def verify(archive_path,destination=None):
    digest=hashlib.sha256(archive_path.read_bytes()).hexdigest()
    expected=archive_path.with_suffix(archive_path.suffix+'.sha256').read_text(encoding='ascii').split()[0]
    if digest!=expected:raise ValueError('Archive checksum mismatch')
    with zipfile.ZipFile(archive_path) as archive:
        if archive.testzip():raise ValueError('CRC mismatch')
        names=[n for n in archive.namelist() if n.endswith('/bundle-manifest.json')]
        if len(names)!=1:raise ValueError('Ambiguous manifest')
        prefix=names[0][:-len('bundle-manifest.json')]
        manifest=json.loads(archive.read(names[0]))
        records=manifest['files']
        if set(archive.namelist())!={names[0],*(prefix+r['path'] for r in records)}:raise ValueError('Undeclared archive entries')
        for record in records:
            data=archive.read(prefix+record['path'])
            if len(data)!=record['bytes'] or hashlib.sha256(data).hexdigest()!=record['sha256']:raise ValueError('File hash mismatch: '+record['path'])
        if destination is not None:
            if destination.exists():raise ValueError('Extraction requires a new directory')
            base=destination.resolve()
            for name in archive.namelist():
                if not (base/name).resolve().is_relative_to(base):raise ValueError('Archive path escapes destination')
            archive.extractall(base)
    return {'sha256':digest,'files_verified':len(records),'version':manifest['version'],
            'extracted_root':str(destination/prefix) if destination else None,'playable':False}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive',type=Path);parser.add_argument('--extract',type=Path)
    args=parser.parse_args();print(json.dumps(verify(args.archive,args.extract),indent=2))
