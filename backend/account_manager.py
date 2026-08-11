import json
from pathlib import Path
from datetime import datetime

ACCOUNTS_FILE = Path("storage/accounts.json")

def load_accounts():
    if not ACCOUNTS_FILE.exists():
        return {}
    try:
        with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_accounts(accounts_data):
    ACCOUNTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
        json.dump(accounts_data, f, indent=4)

def get_accounts():
    """Returns a list of accounts without the raw cookie string for the UI."""
    data = load_accounts()
    accounts = []
    for k, v in data.items():
        accounts.append({
            "name": v.get("name", k),
            "status": v.get("status", "unknown"),
            "last_checked": v.get("last_checked", "")
        })
    return accounts

def get_account_cookies(name: str):
    data = load_accounts()
    return data.get(name, {}).get("cookies_str")

def add_account(name: str, cookies_str: str, status: str = "valid"):
    data = load_accounts()
    data[name] = {
        "name": name,
        "cookies_str": cookies_str,
        "status": status,
        "last_checked": datetime.now().isoformat()
    }
    save_accounts(data)

def delete_account(name: str):
    data = load_accounts()
    if name in data:
        del data[name]
        save_accounts(data)
        return True
    return False

def update_account_status(name: str, status: str):
    data = load_accounts()
    if name in data:
        data[name]["status"] = status
        data[name]["last_checked"] = datetime.now().isoformat()
        save_accounts(data)
        return True
    return False
