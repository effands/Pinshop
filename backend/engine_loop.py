import asyncio
import random
import time
import json
from pathlib import Path
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
            
            from omniflash.generators import generate_image, upload_image, download_image, download_video, generate_video, generate_video_i2v
            import base64
            import os
            
            project_id, _ = bridge.get_active_instance_info()
            if not project_id:
                project_id = "auto"
                
            ref_media_id = None
            if reference_images and len(reference_images) > 0:
                logger_func("> Mengupload gambar referensi ke Google Flow...")
                os.makedirs("storage", exist_ok=True)
                ref_path = "storage/temp_ref.jpg"
                img_data = reference_images[0]
                if "," in img_data:
                    img_data = img_data.split(",", 1)[1]
                
                try:
                    import io
                    from PIL import Image
                    raw_bytes = base64.b64decode(img_data)
                    img = Image.open(io.BytesIO(raw_bytes))
                    if img.mode != 'RGB':
                        img = img.convert('RGB')
                    img.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
                    img.save(ref_path, "JPEG", quality=85)
                except Exception as e:
                    logger_func(f"[Warning] Gagal memproses gambar: {e}")
                    # Fallback to direct save
                    ref_path = "storage/temp_ref.png"
                    with open(ref_path, "wb") as f:
                        f.write(base64.b64decode(img_data))
                
                try:
                    # upload_image might timeout after 45s if ws is stuck
                    ref_media_id = await upload_image(bridge, ref_path, project_id)
                    if ref_media_id:
                        logger_func("> Gambar referensi berhasil diupload.")
                    else:
                        logger_func("[Warning] Gagal mengupload gambar referensi (Result Kosong).")
                except Exception as e:
                    logger_func(f"[Error] Upload gambar referensi gagal/timeout: {e}")
                    # Lanjut tanpa reference image
                    ref_media_id = None

            if media_type == "video":
                logger_func("> Meminta Google Flow merender VIDEO Mahakarya HD...")
                if ref_media_id:
                    results = await generate_video_i2v(bridge, prompt, aspect="9:16", project_id=project_id, image_media_id=ref_media_id)
                else:
                    results = await generate_video(bridge, prompt, aspect="9:16", project_id=project_id)
                
                if not results:
                    logger_func("[Error] Gagal merender video dari Flow.")
                    await asyncio.sleep(30)
                    continue
                    
                video_id = results[0]
                result_path = "storage/generated.mp4"
                await download_video(bridge, video_id, result_path)
            else:
                logger_func("> Meminta Google Flow merender FOTO Mahakarya HD...")
                ref_media_ids = [ref_media_id] if ref_media_id else None
                results = await generate_image(bridge, prompt, aspect="9:16", project_id=project_id, count=1, ref_media_ids=ref_media_ids)
                
                if not results:
                    logger_func("[Error] Gagal merender gambar dari Flow.")
                    await asyncio.sleep(30)
                    continue
                    
                image_url = results[0].get("url") or results[0] # handle string just in case
                if isinstance(image_url, dict): image_url = image_url.get("url")
                result_path = "storage/generated.png"
                await download_image(bridge, image_url, result_path)
            
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
