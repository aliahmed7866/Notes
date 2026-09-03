import os
import sys
from pathlib import Path
from waitress import serve

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import create_app

serve(create_app(),host=os.environ.get("NOTES_BIND_HOST","127.0.0.1"),port=int(os.environ.get("NOTES_PORT","8083")),threads=4)
