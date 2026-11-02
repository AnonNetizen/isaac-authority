"""Run the sealed 36-case UI flow list through the new binary, without menu opt-in."""
import argparse,sys
from pathlib import Path
sys.dont_write_bytecode=True
import run_ui_flow as old
import run_menu_environment as menu
def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    old.EXE,old.REF=menu.EXE,menu.REF;old.invoke=menu.invoke
    sys.exit(0 if old.run(old.MANIFEST,a.output)else 1)
if __name__=='__main__':main()
