"""Freeze a runtime-suite template against unmodified Lua source, without operating the game."""
import argparse
import hashlib
import json
from pathlib import Path

def digest(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source,'sha256').hexdigest()

def freeze(template,game,research,output):
    manifest=json.loads(template.read_text(encoding='utf-8'))
    if manifest['schema']!='isaac-runtime-suite-1':
        raise ValueError('Unknown suite schema')
    manifest['bootstrap_sha256']=digest(research/'research/native_context.lua')
    manifest['enums_sha256']=digest(game/'resources/scripts/enums.lua')
    for case in manifest['cases']:
        for mod in case['mods']:
            base={'game':game,'research':research}[mod['base']].resolve()
            relative=mod['root']
            if not relative or '\\' in relative or ':' in relative or relative.startswith('/') or any(p in ('.','..') for p in relative.split('/')):
                raise ValueError('Mod outside frozen roots')
            root=(base/relative).resolve()
            if not root.is_relative_to(base) or root.is_symlink():
                raise ValueError('Mod outside frozen roots')
            paths=sorted(root.rglob('*.lua'))
            if not (root/'main.lua').is_file() or len(paths)>4096 or sum(p.stat().st_size for p in paths)>32*1024*1024:
                raise ValueError('Invalid frozen mod')
            mod['sha256']={p.relative_to(root).as_posix():digest(p) for p in paths}
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x',encoding='utf-8') as target:
        json.dump(manifest,target,ensure_ascii=True,indent=2)
    return {'manifest':str(output),'sha256':digest(output),'cases':len(manifest['cases'])}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--template',type=Path,required=True)
    parser.add_argument('--game',type=Path,required=True)
    parser.add_argument('--research',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(freeze(args.template,args.game,args.research,args.output)))
