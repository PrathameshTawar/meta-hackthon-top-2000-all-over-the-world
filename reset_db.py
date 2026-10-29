"""
Runner for resetting the Saath demo database from the saath/ directory.
"""
import os
import sys
import subprocess

current_dir = os.path.abspath(os.path.dirname(__file__))
if os.path.exists(os.path.join(current_dir, "backend")):
    backend_dir = os.path.join(current_dir, "backend")
else:
    backend_dir = current_dir

venv_python = os.path.join(backend_dir, ".venv", "Scripts", "python.exe")
python_bin = venv_python if os.path.exists(venv_python) else sys.executable

ret = subprocess.run([python_bin, "-m", "app.db.reset"], cwd=backend_dir)
sys.exit(ret.returncode)
