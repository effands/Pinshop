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
                
            # Process SEO Metadata if available
            seo_title = config.get("seoTitle", "")
            seo_desc = config.get("seoDesc", "")
            reference_images = config.get("referenceImages", [])

            # Get master prompt from UI config
            prompt = config.get("masterPrompt", "")
            
            link = get_random_line(config.get("spintaxLinks", ""))
            media_type = config.get("mediaType", "image")
            
            logger_func(f"> Menyuntikkan Master Prompt: {prompt[:30]}...")
            if reference_images and len(reference_images) > 0:
                logger_func(f"> Menggunakan {len(reference_images)} Gambar Referensi")
            
            if media_type == "video":
                logger_func("> Merender mahakarya VIDEO AI. Sistem standby...")
            else:
                logger_func("> Merender mahakarya FOTO AI. Sistem standby...")
            
            from .bridge_manager import get_bridge, status_snapshot
            bridge = get_bridge()

            # Wait for bridge
            if status_snapshot()["state"] != "ready":
                logger_func("[Warning] Bridge Google Flow belum ready!")
                await asyncio.sleep(10)
                continue
            
            # Call extension to generate ImageFX/VideoFX
            if media_type == "video":
                logger_func("> Proses 'Download' Video Mahakarya HD! (Simulated)")
                await asyncio.sleep(8)
                result_path = str(Path("frontend/public/logo.png").resolve()) 
            else:
                logger_func("> Menunggu flow merender gambar...")
                # Note: Currently bridge.generate_media passes prompt and images to extension
                success = await bridge.generate_media("image", prompt, reference_images)
                if not success:
                    logger_func("[Error] Gagal generate dari Flow. Retry nanti.")
                    await asyncio.sleep(30)
                    continue
                result_path = bridge.get_latest_media()
                if not result_path:
                    logger_func("[Error] File hasil generate tidak ditemukan.")
                    await asyncio.sleep(30)
                    continue

            logger_func(f"> Sukses diunduh: {Path(result_path).name}")
            
            # Target Account
            account_name = config.get("targetAccount")
            if not account_name:
                logger_func("[Error] Tidak ada akun target Pinterest yang dipilih.")
                await asyncio.sleep(30)
                continue
                
            logger_func(f"> Menyiapkan akun Pinterest [{account_name}]...")
            
            # Use SEO Data if present, otherwise fallback to auto-extract or random
            from .spintax import resolve_shopee_title
            product_name = resolve_shopee_title(link) if link else ""

            if seo_title:
                pin_title = seo_title
            elif product_name and product_name != "Rekomendasi Produk Estetik":
                pin_title = product_name
            else:
                pin_title = "Beautiful " + prompt.split(" ")[0] if prompt else "Aesthetic Pin"
            
            if seo_desc:
                pin_desc = seo_desc
            else:
                pin_desc = f"{pin_title}. Dapatkan produk ini dengan klik link di bawah! ✨ #Rekomendasi #Shopee #Aesthetic"

            logger_func("> Membuka Pinterest Pin Creation...")
            from .social.pinterest import upload_to_pinterest
            upload_success = await upload_to_pinterest(
                image_path=result_path,
                title=pin_title[:99],
                description=pin_desc[:499],
                link=link,
                account_name=account_name
            )
            
            if upload_success:
                logger_func(f"✅ PIN BERHASIL: [{account_name}] {pin_title[:30]}...")
                # Clear SEO data from config after successful pin
                if seo_title or seo_desc or (reference_images and len(reference_images) > 0) or prompt:
                    config["seoTitle"] = ""
                    config["seoDesc"] = ""
                    config["masterPrompt"] = ""
                    config["referenceImages"] = []
                    with open(settings.SETTINGS_FILE, "w") as f:
                        json.dump(config, f, indent=4)
            else:
                logger_func(f"❌ PIN GAGAL: [{account_name}]")
                
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
