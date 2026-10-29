#!/usr/bin/env python3
"""Check that built pages load only the install clipboard module and JSON-LD."""
from pathlib import Path
import runpy

if __name__ == '__main__':
    runpy.run_path(str(Path(__file__).resolve().parents[1] / 'scripts/check_install_copy.py'), run_name='__main__')
