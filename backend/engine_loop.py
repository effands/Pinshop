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
            raw_prompt = config.get("masterPrompt", "")
            import re
            # Clean Midjourney flags like --ar 9:16 or --v 6.0 from Google Flow prompt
            prompt = re.sub(r'--[a-zA-Z0-9]+(\s+[^\s]+)?', '', raw_prompt).strip()
            if not prompt:
                prompt = raw_prompt
                
            if not prompt or prompt.strip(".") == "":
                logger_func("[Warning] Master Prompt masih kosong atau tidak valid! Harap isi/generate Master Prompt terlebih dahulu di tab Studio.")
                await asyncio.sleep(15)
                continue
            
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
            
            # Wait up to 10s for real project ID from Chrome extension
            project_id = None
            instance_name = "Chrome"
            
            for _ in range(10):
                instances = bridge.instance_snapshot()
                for inst in instances:
                    pid = inst.get("project_id")
                    if pid and pid != "auto" and pid != "0143adf4-5864-4cb4-abb5-fe4254ad0dc7":
                        project_id = pid
                        instance_name = inst.get("name", "Chrome")
                        break
                if project_id:
                    break
                await asyncio.sleep(1)

            if not project_id:
                logger_func("[Warning] Project ID Google Flow belum terdeteksi! Pastikan tab project Google Flow terbuka di Chrome.")
                await asyncio.sleep(10)
                continue
            
            logger_func(f"> [Google Flow] Project ID: {project_id} | Instance: {instance_name}")
                
            ref_media_id = None
            if reference_images and len(reference_images) > 0:
                logger_func(f"> Mengupload gambar referensi ke Google Flow (Project: {project_id})...")
                os.makedirs("storage", exist_ok=True)
                ref_path = "storage/temp_ref.jpg"
                raw_item = reference_images[0]
                try:
                    import io
                    from PIL import Image
                    import os
                    from pathlib import Path
                    
                    if isinstance(raw_item, str) and (os.path.exists(raw_item) or Path(raw_item).exists()):
                        img = Image.open(raw_item)
                    elif isinstance(raw_item, str) and raw_item.startswith("http"):
                        import urllib.request
                        req = urllib.request.urlopen(raw_item)
                        img = Image.open(io.BytesIO(req.read()))
                    else:
                        img_data = raw_item
                        if "," in img_data:
                            img_data = img_data.split(",", 1)[1]
                        raw_bytes = base64.b64decode(img_data)
                        img = Image.open(io.BytesIO(raw_bytes))
                    
                    if img.mode != 'RGB':
                        img = img.convert('RGB')
                    img.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
                    img.save(ref_path, "JPEG", quality=85)
                except Exception as e:
                    logger_func(f"[Warning] Gagal memproses gambar: {e}")
                    if isinstance(raw_item, str) and os.path.exists(raw_item):
                        ref_path = raw_item
                
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
                generate_count = int(config.get("generateCount", 1))
                logger_func(f"> Mengirim prompt ke Google Flow ImageFX AI ({generate_count}x)...")
                ref_media_ids = [ref_media_id] if ref_media_id else None
                results = await generate_image(bridge, prompt, aspect="portrait", project_id=project_id, count=generate_count, ref_media_ids=ref_media_ids)
                
                if not results:
                    logger_func("[Error] Gagal merender gambar dari Flow.")
                    await asyncio.sleep(30)
                    continue
                    
                logger_func("> Gambar berhasil dirender oleh Google Flow!")
                first_item = results[0]
                image_url = first_item.get("image_url") or first_item.get("url") or (first_item if isinstance(first_item, str) else "")
                result_path = "storage/generated.png"
                logger_func("> Mengunduh file gambar HD ke disk...")
                dl_ok = await download_image(bridge, image_url, result_path)
                if not dl_ok:
                    logger_func("[Warning] Gagal mengunduh gambar hasil render.")
                else:
                    logger_func("> File Foto HD berhasil didownload.")
            
            # Target Account
            account_name = config.get("targetAccount")
            if not account_name:
                logger_func("[Error] Tidak ada akun target Pinterest yang dipilih.")
                await asyncio.sleep(30)
                continue
                
            logger_func(f"> Menyiapkan posting Pinterest untuk akun [{account_name}]...")
            
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

            from .social.pinterest import upload_to_pinterest
            upload_success = await upload_to_pinterest(
                image_path=result_path,
                title=pin_title[:99],
                description=pin_desc[:499],
                link=link,
                account_name=account_name,
                logger_func=logger_func
            )
            
            if upload_success:
                logger_func(f"✅ PIN BERHASIL DIPOSTING: [{account_name}] {pin_title[:30]}...")
                # If a manual prompt was used, automatically stop autopilot to prevent duplicate posts
                if raw_prompt:
                    logger_func("[System] Posting manual berhasil diselesaikan. Menghentikan Autopilot untuk mencegah duplikasi.")
                    _running = False
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
