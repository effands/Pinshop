import asyncio
import sys

# Force UTF-8 output encoding for Windows consoles to prevent charmap UnicodeEncodeError
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

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
import os
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
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
    import datetime
    now = datetime.datetime.now().strftime("%H:%M:%S")
    # Avoid double timestamping if the message already starts with a bracketed time
    if not message.startswith("[20") and not (message.startswith("[") and ":" in message[:10]):
        formatted = f"[{now}] {message}"
    else:
        formatted = message
    try:
        print(formatted)
    except Exception:
        try:
            print(formatted.encode("ascii", "replace").decode("ascii"))
        except Exception:
            pass
    # create task to broadcast safely
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(manager.broadcast(json.dumps({"type": "log", "message": formatted})))
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

os.makedirs("storage/gallery", exist_ok=True)
app.mount("/gallery", StaticFiles(directory="storage/gallery"), name="gallery")

@app.get("/api/gallery")
async def get_gallery():
    gallery_dir = Path("storage/gallery")
    gallery_dir.mkdir(parents=True, exist_ok=True)
    files = []
    for f in sorted(gallery_dir.glob("*"), key=os.path.getmtime, reverse=True):
        if f.is_file() and f.suffix.lower() in {".png", ".jpg", ".jpeg", ".mp4"}:
            meta_path = f.with_name(f.name + ".json")
            meta_data = {}
            if meta_path.exists():
                try:
                    with open(meta_path, "r", encoding="utf-8") as mf:
                        meta_data = json.load(mf)
                except Exception:
                    pass
            files.append({
                "filename": f.name,
                "url": f"/gallery/{f.name}",
                "type": "video" if f.suffix.lower() == ".mp4" else "image",
                "size": f.stat().st_size,
                "created_at": os.path.getmtime(f),
                "meta": meta_data
            })
    return {"success": True, "files": files}

@app.delete("/api/gallery/{filename}")
async def delete_gallery_item(filename: str):
    file_path = Path("storage/gallery") / filename
    try:
        resolved_base = Path("storage/gallery").resolve()
        resolved_file = file_path.resolve()
        if not resolved_file.is_relative_to(resolved_base):
            return {"success": False, "error": "Access denied"}
    except Exception:
        return {"success": False, "error": "Invalid path"}
        
    if file_path.exists():
        file_path.unlink()
        meta_path = file_path.with_name(file_path.name + ".json")
        if meta_path.exists():
            try:
                meta_path.unlink()
            except Exception:
                pass
        return {"success": True}
    return {"success": False, "error": "File not found"}

class DeleteBatchRequest(BaseModel):
    filenames: List[str]

@app.post("/api/gallery/delete-batch")
async def delete_gallery_batch(req: DeleteBatchRequest):
    success_count = 0
    resolved_base = Path("storage/gallery").resolve()
    for filename in req.filenames:
        try:
            file_path = Path("storage/gallery") / filename
            resolved_file = file_path.resolve()
            if resolved_file.is_relative_to(resolved_base) and file_path.exists():
                file_path.unlink()
                meta_path = file_path.with_name(file_path.name + ".json")
                if meta_path.exists():
                    try:
                        meta_path.unlink()
                    except Exception:
                        pass
                success_count += 1
        except Exception:
            pass
    return {"success": True, "deleted": success_count}

@app.websocket("/ws")
async def extension_ws(websocket: WebSocket):
    await websocket.accept()
    send_log("Extension connecting via WebSocket...")
    from . import bridge_manager
    bridge = bridge_manager.get_bridge()
    await bridge.handle_fastapi_ws(websocket)

@app.post("/api/ext/callback")
async def extension_callback(body: dict):
    from . import bridge_manager
    bridge = bridge_manager.get_bridge()
    return {"ok": bridge.handle_http_callback(body)}

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
    try:
        from .bridge_manager import status_snapshot
        flow_count = status_snapshot().get("total_connected_profiles", 0)
    except Exception:
        flow_count = 0
    from .engine_loop import is_autopilot_running
    return {"status": "online", "flowCount": flow_count, "autopilotRunning": is_autopilot_running()}

from typing import Dict, Any

@app.post("/api/save-config")
async def save_config(config: Dict[str, Any]):
    with open(settings.SETTINGS_FILE, "w") as f:
        json.dump(config, f, indent=4)
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

from typing import Dict, Any, List, Optional

class QueueItem(BaseModel):
    id: str
    basicTitle: str
    spintaxLinks: str
    referenceImages: List[str]
    status: str = "pending"
    seoTitle: Optional[str] = None
    seoDesc: Optional[str] = None
    masterPrompt: Optional[str] = None

@app.get("/api/queue")
async def get_queue_list():
    config = {}
    if settings.SETTINGS_FILE.exists():
        with open(settings.SETTINGS_FILE, "r") as f:
            try:
                config = json.load(f)
            except:
                pass
    queue_list = config.get("queue", [])
    return {"success": True, "queue": queue_list}

@app.post("/api/queue")
async def add_queue_item(item: QueueItem):
    config = {}
    if settings.SETTINGS_FILE.exists():
        with open(settings.SETTINGS_FILE, "r") as f:
            try:
                config = json.load(f)
            except:
                pass
    if "queue" not in config:
        config["queue"] = []
    config["queue"].append(item.dict())
    with open(settings.SETTINGS_FILE, "w") as f:
        json.dump(config, f, indent=4)
    return {"success": True}

@app.delete("/api/queue/{item_id}")
async def delete_queue_item(item_id: str):
    config = {}
    if settings.SETTINGS_FILE.exists():
        with open(settings.SETTINGS_FILE, "r") as f:
            try:
                config = json.load(f)
            except:
                pass
    if "queue" in config:
        config["queue"] = [i for i in config["queue"] if i.get("id") != item_id]
        with open(settings.SETTINGS_FILE, "w") as f:
            json.dump(config, f, indent=4)
    return {"success": True}

@app.put("/api/queue/{item_id}")
async def update_queue_item(item_id: str, updated_item: QueueItem):
    config = {}
    if settings.SETTINGS_FILE.exists():
        with open(settings.SETTINGS_FILE, "r") as f:
            try:
                config = json.load(f)
            except:
                pass
    if "queue" in config:
        for idx, i in enumerate(config["queue"]):
            if i.get("id") == item_id:
                data = updated_item.dict()
                data["id"] = item_id
                data["status"] = i.get("status", "pending")
                config["queue"][idx] = data
                break
        with open(settings.SETTINGS_FILE, "w") as f:
            json.dump(config, f, indent=4)
    return {"success": True}

@app.post("/api/queue/clear")
async def clear_queue():
    config = {}
    if settings.SETTINGS_FILE.exists():
        with open(settings.SETTINGS_FILE, "r") as f:
            try:
                config = json.load(f)
            except:
                pass
    config["queue"] = []
    with open(settings.SETTINGS_FILE, "w") as f:
        json.dump(config, f, indent=4)
    return {"success": True}

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
    imagesBase64: list[str] = []
    basicTitle: str

@app.post("/api/generate-seo-prompt")
async def api_generate_seo_prompt(req: GenerateSeoPromptRequest):
    from .gemini_manager import manager
    import os, uuid, base64
    from pathlib import Path
    try:
        # Generate prompt from Gemini
        result = manager.generate_prompt_from_image(req.imagesBase64, req.basicTitle)
        
        saved_images = []
        uploads_dir = Path("storage/uploads")
        uploads_dir.mkdir(parents=True, exist_ok=True)

        for b64_str in req.imagesBase64:
            if b64_str:
                filename = f"ref_{uuid.uuid4().hex[:8]}.jpg"
                filepath = uploads_dir / filename
                
                # Clean base64 header
                b64_data = b64_str
                if "," in b64_data:
                    b64_data = b64_data.split(",", 1)[1]
                    
                with open(filepath, "wb") as f:
                    f.write(base64.b64decode(b64_data))
                    
                saved_images.append(str(filepath.resolve()))
                
        result["reference_images"] = saved_images
            
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

class BulkGeneratorRequest(BaseModel):
    theme: str
    shopeeLink: str
    count: int = 5

@app.post("/api/generate-bulk-ideas")
async def api_generate_bulk_ideas(req: BulkGeneratorRequest):
    if not req.theme.strip():
        return {"success": False, "error": "Tema tidak boleh kosong"}
    
    # 1. Brainstorm ideas
    try:
        from .gemini_manager import manager
        ideas = await asyncio.to_thread(manager.brainstorm_ideas, req.theme, req.count)
    except Exception as e:
        return {"success": False, "error": f"Gagal memikirkan ide: {str(e)}"}
    
    if not ideas:
        return {"success": False, "error": "AI tidak mengembalikan ide apa pun."}
    
    # 2. For each idea, generate SEO title, description, and master prompt
    import time
    import random
    
    new_items = []
    for idea in ideas:
        try:
            # Generate SEO data from Gemini
            seo_data = await asyncio.to_thread(manager.generate_seo_and_prompt, idea, [])
            item_id = f"q_{int(time.time() * 1000)}_{random.randint(100, 999)}"
            new_items.append({
                "id": item_id,
                "basicTitle": idea,
                "spintaxLinks": req.shopeeLink,
                "referenceImages": [],
                "status": "pending",
                "seoTitle": seo_data.get("seo_title", ""),
                "seoDesc": seo_data.get("seo_desc", ""),
                "masterPrompt": seo_data.get("master_prompt", "")
            })
        except Exception as e:
            # If one fails, we can skip or log
            logger.error(f"Failed to generate SEO for idea '{idea}': {e}")
            continue

    if not new_items:
        return {"success": False, "error": "Gagal menghasilkan detail SEO untuk semua ide."}

    # 3. Load settings, append items, and save
    config = {}
    if settings.SETTINGS_FILE.exists():
        with open(settings.SETTINGS_FILE, "r") as f:
            try:
                config = json.load(f)
            except:
                pass
    
    queue = config.get("queue", [])
    queue.extend(new_items)
    config["queue"] = queue
    
    with open(settings.SETTINGS_FILE, "w") as f:
        json.dump(config, f, indent=4)
        
    send_log(f"[System] AI berhasil men-generate & memasukkan {len(new_items)} ide promosi baru ke dalam antrean.")
    return {"success": True, "count": len(new_items)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host=settings.HOST, port=settings.PORT, reload=True)

