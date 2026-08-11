import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
ENGINE_DIR = ROOT_DIR / "engine"
FRONTEND_DIR = ROOT_DIR / "frontend"
STORAGE_DIR = ROOT_DIR / "storage"
DATA_DIR = ROOT_DIR / "data"
SETTINGS_FILE = DATA_DIR / "settings.json"

STORAGE_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

HOST = os.environ.get("PINSHOP_HOST", "127.0.0.1")
PORT = int(os.environ.get("PINSHOP_PORT", "8015"))

def get_flow_extension_instance_id() -> str:
    # Optional logic to pick extension instance if running multiple profiles.
    return "default"
