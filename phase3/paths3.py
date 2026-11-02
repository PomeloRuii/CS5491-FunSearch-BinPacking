"""Relocate immutable historical receipt paths without rewriting their contents."""
from pathlib import Path
import bootstrap3
from bootstrap3 import PROJECT

def recorded_path(value):
    path=Path(value)
    if path.exists():return path
    normal=str(value).replace('\\','/')
    for anchor in ('phase1b','phase2','phase3','output'):
        marker='/'+anchor+'/'
        if marker in normal:
            relative=anchor+'/'+normal.split(marker,1)[1]
            target=(PROJECT/relative).resolve()
            if target.is_relative_to(PROJECT) and target.exists():return target
    raise FileNotFoundError('Receipt target unavailable in this checkout: '+normal)
