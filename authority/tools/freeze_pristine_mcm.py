"""Recover a unique pre-experiment source for CLI only; do not write installed mods."""
import difflib,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
import run_ui_flow as f
ROOT=f.ROOT;TARGET=ROOT/'research/menu_environment/pristine_modconfig.lua'
def freeze():
    old=ROOT/'research/slice3_ui_inputs/mods/mod_config_menu_cn_2494192799/scripts/modconfig.lua'
    game=Path(f.load(ROOT/'research/sprite_state/profile.json')['game_root'])
    backup=game/'mods/mod_config_menu_cn_2494192799/scripts/modconfig.lua.iodg.bak'
    a=backup.read_bytes();b=old.read_bytes()
    assert f.digest(backup)=='19a0366d7db6faae98a94dd46c5111f5ec4e5d4dc1bc456cb7fd3cacac3ffaf2'
    assert f.digest(old)=='3ace42aed3a2a74fa6d8dbc1b225aa2470b6cbcd92204b800187811fe0ea37ce'
    aa=a.splitlines(keepends=True);bb=b.splitlines(keepends=True)
    diff=[op for op in difflib.SequenceMatcher(a=aa,b=bb,autojunk=False).get_opcodes()if op[0]!='equal']
    assert len(diff)==1 and diff[0][0]=='insert'
    _,i,j,k,l=diff[0];insert=b''.join(bb[k:l]);assert i==j and b'Isaac Online Desync Guard: online menu guard'in insert and b'Game():GetNumPlayers() > 1'in insert
    f.parent.frozen(TARGET,a)
    proof=dict(schema='pristine-mcm-baseline-1',backup_path=str(backup),backup_sha256=f.digest(backup),historical_frozen_sha256=f.digest(old),executed_source=TARGET.relative_to(ROOT).as_posix(),executed_sha256=f.digest(TARGET),difference='historical frozen file has exactly one inserted experimental online-menu-guard block',inserted_bytes=len(insert),inserted_sha256=__import__('hashlib').sha256(insert).hexdigest(),source_bytes_copied=len(a),game_files_written=0,upstream_distribution_proven=False)
    f.freeze_json(ROOT/'research/menu_environment/pristine_mcm_proof.json',proof)
    print(json.dumps(dict(prior_patch_identified=True,backup_bytes_unchanged=True,game_files_written=0)))
if __name__=='__main__':freeze()
