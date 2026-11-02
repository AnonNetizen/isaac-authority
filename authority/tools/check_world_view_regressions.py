"""Run the sealed menu model list without enabling the new world view."""
import argparse,sys
from pathlib import Path
sys.dont_write_bytecode=True
import run_menu_environment as old
import run_world_view as new
def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();old.EXE,old.REF=new.EXE,new.REF;old.invoke=new.invoke
    sys.exit(0 if old.run(old.MANIFEST,a.output)else 1)
if __name__=='__main__':main()
