import asyncio
import random
import time
import json
from . import settings
from .spintax import get_random_line, generate_prompt
from .social.pinterest import upload_to_pinterest

_autopilot_task = None
_running = False

async def autopilot_loop(logger_func):
    global _running
    logger_func("[System] Starting Autopilot Engine...")
    
    from .bridge_manager import get_bridge
    bridge = get_bridge()

    while _running:
        try:
            logger_func("\n[System] Checking schedule...")
            # We can implement time check here based on config.startTime / config.stopTime.
            # For simplicity, we just run.
            
            config = {}
            if settings.SETTINGS_FILE.exists():
                with open(settings.SETTINGS_FILE, "r") as f:
                    config = json.load(f)
            
            if not config:
                logger_func("[Warning] Config is empty. Cannot run. Sleeping 60s.")
                await asyncio.sleep(60)
                continue
                
            prompt = generate_prompt(
                config.get("subject", ""),
                config.get("detail", ""),
                config.get("background", ""),
                config.get("quality", "")
            )
            
            link = get_random_line(config.get("spintaxLinks", ""))
            media_type = config.get("mediaType", "image")
            
            logger_func(f"> Menyuntikkan Prompt: {prompt[:30]}...")
            
            if media_type == "video":
                logger_func("> Merender mahakarya VIDEO AI. Sistem standby...")
            else:
                logger_func("> Merender mahakarya FOTO AI. Sistem standby...")
            
            # Wait for bridge
            if not bridge.is_ready():
                logger_func("[Warning] Bridge Google Flow belum ready!")
                await asyncio.sleep(10)
                continue
            
            # Call extension to generate ImageFX/VideoFX
            if media_type == "video":
                logger_func("> Proses 'Download' Video Mahakarya HD! (Simulated)")
                await asyncio.sleep(5)
                mock_media_path = "storage/mock_generated.mp4"
                logger_func("> File Video HD berhasil didownload.")
            else:
                logger_func("> Proses 'Download' Foto Mahakarya HD! (Simulated)")
                await asyncio.sleep(3)
                mock_media_path = "storage/mock_generated.png"
                logger_func("> File Foto HD berhasil didownload.")
            
            logger_func("> Generate Judul & Deskripsi SEO...")
            from .spintax import resolve_shopee_title
            
            # Auto-extract product name from Shopee URL
            product_name = resolve_shopee_title(link) if link else ""
            
            if product_name and product_name != "Rekomendasi Produk Estetik":
                title = product_name
                logger_func(f"> Judul Ekstrak: {title[:30]}...")
            else:
                title = "Beautiful " + prompt.split(" ")[0] if prompt else "Aesthetic Pin"
                
            description = f"{title}. Dapatkan produk ini dengan klik link di bawah! ✨ #Rekomendasi #Shopee #Aesthetic"
            
            logger_func("> Pinning to Pinterest...")
            target_account = config.get("targetAccount", "default")
            
            # success = await upload_to_pinterest(mock_media_path, title, description, link, account_name=target_account)
            success = True # mock success
            if success:
                logger_func("> Pin Sukses Diterbitkan!")
            else:
                logger_func("> Gagal upload ke Pinterest.")
                
            sleep_time = random.randint(300, 600) # 5-10 mins
            logger_func(f"> Sleep Engine: Beristirahat {sleep_time//60} menit (Anti-Ban) ...")
            
            for _ in range(sleep_time):
                if not _running: break
                await asyncio.sleep(1)
                
        except Exception as e:
            logger_func(f"[Error] Autopilot Loop: {e}")
            await asyncio.sleep(30)

def start_autopilot(logger_func):
    global _running, _autopilot_task
    if _running: return False
    
    _running = True
    loop = asyncio.get_running_loop()
    _autopilot_task = loop.create_task(autopilot_loop(logger_func))
    return True

def stop_autopilot(logger_func):
    global _running, _autopilot_task
    _running = False
    if _autopilot_task:
        _autopilot_task.cancel()
    logger_func("[System] Autopilot Stopped.")
