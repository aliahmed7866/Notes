import json
import os
import subprocess
import sys
from pathlib import Path

def test_admin_registration_uses_actual_waitress_process(tmp_path):
    registry=tmp_path/"apps.json"
    env={**os.environ,"NOTES_APP_DIR":str(tmp_path/"Notes")}
    subprocess.run([sys.executable,str(Path(__file__).parents[1]/"termux"/"register-admin.py"),str(registry),"8083"],check=True,env=env)
    app=json.loads(registry.read_text())["apps"][0]
    assert app["id"]=="notes"
    assert app["service"]=="notes"
    assert app["port"]==8083
    assert app["process_match"]==f"{tmp_path}/Notes/.venv/bin/python termux/run-web.py"
