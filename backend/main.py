import asyncio
import sys

# Silence Windows asyncio ProactorEventLoop spamming WinError 10054 ConnectionResetError
if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except Exception:
        pass
    from asyncio.proactor_events import _ProactorBasePipeTransport
    _orig_call_connection_lost = _ProactorBasePipeTransport._call_connection_lost

    def _call_connection_lost_patched(self, exc):
        try:
            _orig_call_connection_lost(self, exc)
        except ConnectionResetError:
            pass
        except Exception:
            raise

    _ProactorBasePipeTransport._call_connection_lost = _call_connection_lost_patched

import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

from . import settings
from .bridge_manager import init_bridge, close_bridge

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except:
                pass

manager = ConnectionManager()

def send_log(message: str):
    print(message)
    # create task to broadcast safely
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(manager.broadcast(json.dumps({"type": "log", "message": message})))
    except RuntimeError:
        pass

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Setup
    print("\n\033[96m") # Cyan color
    print("    ___    __________________    ________  ___ ")
    print("   /   |  / ____/ ____/  _/ /   /  _/ __ |/   |")
    print("  / /| | / /_  / /_   / // /    / // /_/ / /| |")
    print(" / ___ |/ __/ / __/ _/ // /____/ // __  / ___ |")
    print("/_/  |_/_/   /_/   /___/_____/___/_/ |_/_/  |_|")
    print("\033[0m")
    print("====================================================")
    print("       PINSHOP EDITION - AUTO PINTEREST PIN")
    print("====================================================\n")
    send_log("[System] PinShop Engine Starting...")
    try:
        await init_bridge()
        send_log("[System] Google Flow Extension Bridge initialized.")
    except Exception as e:
        send_log(f"[Error] Failed to init bridge: {e}")
        
    yield
    # Teardown
    send_log("[System] PinShop Engine Shutting down...")
    await close_bridge()

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.websocket("/ws")
async def extension_ws(websocket: WebSocket):
    await websocket.accept()
    send_log("Extension connecting via WebSocket...")
    from . import bridge_manager
    bridge = bridge_manager.get_bridge()
    await bridge.handle_fastapi_ws(websocket)

@app.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.get("/api/status")
async def get_status():
    return {"status": "online"}

class ConfigModel(BaseModel):
    startTime: str
    stopTime: str
    targetPost: int
    mediaType: str
    spintaxLinks: str
    geminiApiKeys: str
    subject: str
    detail: str
    background: str
    quality: str

@app.post("/api/save-config")
async def save_config(config: ConfigModel):
    with open(settings.SETTINGS_FILE, "w") as f:
        f.write(config.model_dump_json())
    send_log("[System] Configuration saved successfully.")
    return {"success": True}

@app.get("/api/get-config")
async def get_config():
    if settings.SETTINGS_FILE.exists():
        with open(settings.SETTINGS_FILE, "r") as f:
            try:
                return json.load(f)
            except:
                pass
    return {}

class GeminiTestRequest(BaseModel):
    apiKey: str

@app.post("/api/test-gemini")
async def test_gemini(req: GeminiTestRequest):
    from .gemini_manager import manager
    is_valid = manager.test_key(req.apiKey)
    return {"valid": is_valid}

class GeneratePromptRequest(BaseModel):
    niche: str

@app.post("/api/generate-prompts")
async def api_generate_prompts(req: GeneratePromptRequest):
    from .gemini_manager import manager
    try:
        result = manager.generate_prompt(req.niche)
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "error": str(e)}

class GenerateSeoPromptRequest(BaseModel):
    imageBase64: str = ""
    basicTitle: str

@app.post("/api/generate-seo-prompt")
async def api_generate_seo_prompt(req: GenerateSeoPromptRequest):
    from .gemini_manager import manager
    import os, uuid, base64
    try:
        # Generate prompt from Gemini
        result = manager.generate_prompt_from_image(req.imageBase64, req.basicTitle)
        
        # Save image to disk for Flow reference only if image is provided
        if req.imageBase64:
            uploads_dir = Path("storage/uploads")
            uploads_dir.mkdir(parents=True, exist_ok=True)
            filename = f"ref_{uuid.uuid4().hex[:8]}.jpg"
            filepath = uploads_dir / filename
            
            # Clean base64 header
            b64_data = req.imageBase64
            if "," in b64_data:
                b64_data = b64_data.split(",", 1)[1]
                
            with open(filepath, "wb") as f:
                f.write(base64.b64decode(b64_data))
                
            result["reference_image"] = str(filepath.resolve())
        else:
            result["reference_image"] = ""
            
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "error": str(e)}

from .engine_loop import start_autopilot, stop_autopilot

@app.post("/api/start-autopilot")
async def api_start_autopilot():
    success = start_autopilot(send_log)
    if success:
        return {"status": "started"}
    return {"status": "already_running"}

@app.post("/api/stop-autopilot")
async def api_stop_autopilot():
    stop_autopilot(send_log)
    return {"status": "stopped"}

from .social.pinterest import manual_login

@app.post("/api/auth-setup")
async def api_auth_setup():
    send_log("[System] Membuka browser untuk otorisasi Pinterest...")
    # Run in background so we don't block
    loop = asyncio.get_running_loop()
    loop.create_task(manual_login())
    return {"status": "browser_opened"}

class CookieRequest(BaseModel):
    cookies: str
    accountName: str = "default"

@app.post("/api/auth-cookie")
async def api_auth_cookie(req: CookieRequest):
    from .social.pinterest import inject_cookies
    from . import account_manager
    
    if not req.accountName.strip():
        return {"success": False, "error": "Nama Akun tidak boleh kosong"}
        
    try:
        count = len(json.loads(req.cookies))
    except:
        count = 0
        
    # inject_cookies now returns boolean (is_valid)
    is_valid = await inject_cookies(req.cookies, account_name=req.accountName)
    status_str = "valid" if is_valid else "expired"
    
    account_manager.add_account(req.accountName, req.cookies, status=status_str)
    
    if is_valid:
        send_log(f"[System] Berhasil menyuntikkan & validasi {count} Cookies untuk Akun '{req.accountName}'.")
        return {"success": True, "count": count, "status": "valid"}
    else:
        send_log(f"[System] Warning: Cookies untuk Akun '{req.accountName}' terinjeksi namun terdeteksi Expired/Invalid.")
        return {"success": True, "count": count, "status": "expired"}

@app.get("/api/accounts")
async def api_get_accounts():
    from . import account_manager
    return {"success": True, "accounts": account_manager.get_accounts()}

@app.delete("/api/accounts/{account_name}")
async def api_delete_account(account_name: str):
    from . import account_manager
    success = account_manager.delete_account(account_name)
    return {"success": success}

class AccountCheckRequest(BaseModel):
    accountName: str

@app.post("/api/accounts/check")
async def api_check_account(req: AccountCheckRequest):
    from . import account_manager
    from .social.pinterest import inject_cookies
    
    cookies_str = account_manager.get_account_cookies(req.accountName)
    if not cookies_str:
        return {"success": False, "error": "Account not found"}
        
    is_valid = await inject_cookies(cookies_str, account_name=req.accountName)
    status_str = "valid" if is_valid else "expired"
    account_manager.update_account_status(req.accountName, status_str)
    
    return {"success": True, "status": status_str}

class TestAllGeminiRequest(BaseModel):
    keys: str

@app.post("/api/test-gemini-all")
async def api_test_gemini_all(req: TestAllGeminiRequest):
    from .gemini_manager import manager
    import asyncio
    
    raw_keys = []
    for k in req.keys.split('\n'):
        cleaned = k.strip().replace(" ✅", "").replace(" ❌", "")
        if cleaned:
            raw_keys.append(cleaned)
            
    if not raw_keys:
        return {"success": False, "keys": ""}
        
    results = []
    
    # Test all keys concurrently
    async def test_single(key):
        is_valid = await asyncio.to_thread(manager.test_key, key)
        return {"key": key, "valid": is_valid}
        
    tasks = [test_single(k) for k in raw_keys]
    outcomes = await asyncio.gather(*tasks)
    
    # Sort: active first, then invalid, appending symbols
    active_keys = [f'{o["key"]} ✅' for o in outcomes if o["valid"]]
    invalid_keys = [f'{o["key"]} ❌' for o in outcomes if not o["valid"]]
    
    sorted_keys = active_keys + invalid_keys
    
    return {
        "success": True,
        "sortedKeys": "\n".join(sorted_keys),
        "activeCount": len(active_keys),
        "invalidCount": len(invalid_keys)
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host=settings.HOST, port=settings.PORT, reload=True)

