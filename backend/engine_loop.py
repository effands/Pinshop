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
                
            # Check for pending queue items first
            queue = config.get("queue", [])
            active_queue_item = None
            for idx, item in enumerate(queue):
                if item.get("status") == "pending":
                    active_queue_item = item
                    break

            is_queue_mode = active_queue_item is not None

            if is_queue_mode:
                logger_func(f"\n[Queue] Memproses item antrean: {active_queue_item.get('basicTitle')} (ID: {active_queue_item.get('id')})")
                
                # Mark item as running
                active_queue_item["status"] = "running"
                with open(settings.SETTINGS_FILE, "w") as f:
                    json.dump(config, f, indent=4)
                
                # If custom SEO metadata is already stored in the queue item, use it directly!
                if active_queue_item.get("seoTitle") and active_queue_item.get("masterPrompt"):
                    logger_func("> Menggunakan SEO & Prompt kustom yang sudah tersimpan di antrean.")
                    seo_title = active_queue_item.get("seoTitle", "")
                    seo_desc = active_queue_item.get("seoDesc", "")
                    raw_prompt = active_queue_item.get("masterPrompt", "")
                    reference_images = active_queue_item.get("referenceImages", [])
                    link = active_queue_item.get("spintaxLinks", "")
                else:
                    logger_func("> Menghubungi Gemini AI untuk meracik SEO & Prompt Spintax...")
                    from .gemini_manager import manager as gemini_manager
                    try:
                        res = gemini_manager.generate_seo_and_prompt(
                            active_queue_item.get("basicTitle", ""),
                            active_queue_item.get("referenceImages", [])
                        )
                        seo_title = res.get("seo_title", "")
                        seo_desc = res.get("seo_desc", "")
                        raw_prompt = res.get("master_prompt", "")
                        reference_images = active_queue_item.get("referenceImages", [])
                        link = active_queue_item.get("spintaxLinks", "")
                        logger_func("> Gemini sukses meracik data untuk antrean ini.")
                    except Exception as ge:
                        logger_func(f"[Error] Gemini gagal memproses antrean: {ge}")
                        active_queue_item["status"] = "failed"
                        with open(settings.SETTINGS_FILE, "w") as f:
                            json.dump(config, f, indent=4)
                        await asyncio.sleep(10)
                        continue
            else:
                # Manual Studio post mode
                seo_title = config.get("seoTitle", "")
                seo_desc = config.get("seoDesc", "")
                reference_images = config.get("referenceImages", [])
                raw_prompt = config.get("masterPrompt", "")
                link = get_random_line(config.get("spintaxLinks", ""))

            import re
            # Clean Midjourney flags like --ar 9:16 or --v 6.0 from Google Flow prompt
            prompt = re.sub(r'--[a-zA-Z0-9]+(\s+[^\s]+)?', '', raw_prompt).strip()
            if not prompt:
                prompt = raw_prompt
                
            from .spintax import parse_spintax
            prompt = parse_spintax(prompt)
                
            if not prompt or prompt.strip(".") == "":
                if is_queue_mode:
                    logger_func("[Error] Hasil prompt dari Gemini kosong. Melewati antrean ini.")
                    active_queue_item["status"] = "failed"
                    with open(settings.SETTINGS_FILE, "w") as f:
                        json.dump(config, f, indent=4)
                else:
                    logger_func("[Warning] Master Prompt masih kosong atau tidak valid! Harap isi/generate Master Prompt terlebih dahulu di tab Studio.")
                    await asyncio.sleep(15)
                continue
            
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

            selected_video_ratio = config.get("videoRatio", "9:16")
            selected_video_duration = int(config.get("videoDuration", "10s").replace("s", ""))
            
            image_ratio_map = {
                "16:9": "landscape",
                "4:3": "4x3",
                "1:1": "square",
                "3:4": "3x4",
                "9:16": "portrait"
            }
            selected_image_ratio = image_ratio_map.get(config.get("imageRatio", "9:16"), "portrait")

            if media_type == "video":
                logger_func(f"> Meminta Google Flow merender VIDEO ({selected_video_ratio}, {selected_video_duration}s) Mahakarya HD...")
                if ref_media_id:
                    results = await generate_video_i2v(
                        bridge, prompt, 
                        aspect=selected_video_ratio, 
                        project_id=project_id, 
                        image_media_id=ref_media_id,
                        duration=selected_video_duration
                    )
                else:
                    results = await generate_video(
                        bridge, prompt, 
                        aspect=selected_video_ratio, 
                        project_id=project_id,
                        duration=selected_video_duration
                    )
                
                if not results:
                    logger_func("[Error] Gagal merender video dari Flow.")
                    await asyncio.sleep(30)
                    continue
                media_files = [{"type": "video", "item": results[0]}]
            else:
                generate_count = int(config.get("generateCount", 1))
                logger_func(f"> Mengirim prompt ke Google Flow ImageFX AI (Total target: {generate_count}x)...")
                ref_media_ids = [ref_media_id] if ref_media_id else None
                
                results = []
                remaining = generate_count
                batch_idx = 1
                while remaining > 0:
                    current_batch = min(4, remaining)
                    logger_func(f"> Mengirim batch ke-{batch_idx} ({current_batch} gambar) ke Google Flow...")
                    batch_results = await generate_image(bridge, prompt, aspect=selected_image_ratio, project_id=project_id, count=current_batch, ref_media_ids=ref_media_ids)
                    if batch_results:
                        results.extend(batch_results)
                        logger_func(f"  Batch ke-{batch_idx} sukses. Total terkumpul: {len(results)} gambar.")
                    else:
                        logger_func(f"[Warning] Batch ke-{batch_idx} gagal merender.")
                    
                    remaining -= current_batch
                    batch_idx += 1
                    if remaining > 0:
                        await asyncio.sleep(2) # Small safety delay between batches
                
                if not results:
                    logger_func("[Error] Gagal merender gambar sama sekali dari Flow.")
                    await asyncio.sleep(30)
                    continue
                logger_func(f"> Total {len(results)} gambar berhasil dirender oleh Google Flow!")
                media_files = [{"type": "image", "item": r} for r in results]

            # Target Account
            account_name = config.get("targetAccount")
            if not account_name:
                logger_func("[Error] Tidak ada akun target Pinterest yang dipilih.")
                await asyncio.sleep(30)
                continue

            for idx, media_file in enumerate(media_files):
                if not _running: break
                
                # 1. Download & Save to Gallery
                if media_file["type"] == "video":
                    video_id = media_file["item"]
                    result_path = "storage/generated.mp4"
                    await download_video(bridge, video_id, result_path)
                    try:
                        import shutil
                        os.makedirs("storage/gallery", exist_ok=True)
                        gallery_filename = f"gallery_{int(time.time())}.mp4"
                        shutil.copy(result_path, f"storage/gallery/{gallery_filename}")
                    except Exception as e:
                        logger_func(f"[Warning] Gagal menyalin video ke gallery: {e}")
                else:
                    first_item = media_file["item"]
                    image_url = first_item.get("image_url") or first_item.get("url") or (first_item if isinstance(first_item, str) else "")
                    result_path = "storage/generated.png"
                    logger_func(f"> Mengunduh file gambar HD ke-{idx+1} ke disk...")
                    dl_ok = await download_image(bridge, image_url, result_path)
                    if not dl_ok:
                        logger_func(f"[Warning] Gagal mengunduh gambar ke-{idx+1}.")
                        continue
                    else:
                        logger_func(f"> File Foto HD ke-{idx+1} berhasil didownload.")
                        try:
                            import shutil
                            os.makedirs("storage/gallery", exist_ok=True)
                            gallery_filename = f"gallery_{int(time.time())}_{idx}.png"
                            shutil.copy(result_path, f"storage/gallery/{gallery_filename}")
                        except Exception as e:
                            logger_func(f"[Warning] Gagal menyalin gambar ke gallery: {e}")

                # 2. Prepare Pinterest Title and Description (with Spintax)
                logger_func(f"> Menyiapkan posting Pinterest ({idx+1}/{len(media_files)}) untuk akun [{account_name}]...")
                from .spintax import resolve_shopee_title, parse_spintax
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

                # Parse Spintax fresh for each post!
                pin_title = parse_spintax(pin_title)
                pin_desc = parse_spintax(pin_desc)

                # 3. Post to Pinterest
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
                    logger_func(f"✅ PIN BERHASIL DIPOSTING ({idx+1}/{len(media_files)}): [{account_name}] {pin_title[:30]}...")
                else:
                    logger_func(f"❌ PIN GAGAL ({idx+1}/{len(media_files)}): [{account_name}]")

                # 4. Sleep interval between multiple posts
                if idx < len(media_files) - 1:
                    sleep_time = int(config.get("sleepInterval", 10))
                    if sleep_time >= 60:
                        logger_func(f"> Sleep Jeda: Beristirahat {sleep_time//60} menit sebelum posting berikutnya...")
                    else:
                        logger_func(f"> Sleep Jeda: Beristirahat {sleep_time} detik sebelum posting berikutnya...")
                    for _ in range(sleep_time):
                        if not _running: break
                        await asyncio.sleep(1)

            # If a queue item was processed, update its final status!
            if is_queue_mode:
                active_queue_item["status"] = "success" if upload_success else "failed"
                try:
                    if settings.SETTINGS_FILE.exists():
                        with open(settings.SETTINGS_FILE, "r") as f:
                            fresh_config = json.load(f)
                        for i in fresh_config.get("queue", []):
                            if i.get("id") == active_queue_item["id"]:
                                i["status"] = active_queue_item["status"]
                        with open(settings.SETTINGS_FILE, "w") as f:
                            json.dump(fresh_config, f, indent=4)
                    logger_func(f"[Queue] Status antrean diupdate: {active_queue_item['status'].upper()}")
                except Exception as err:
                    logger_func(f"[Warning] Gagal mengupdate status antrean: {err}")
            
            # If a manual prompt was used, automatically stop autopilot after posting all generated variations
            if not is_queue_mode and raw_prompt:
                logger_func("[System] Posting manual seluruh variasi selesai. Menghentikan Autopilot untuk mencegah duplikasi.")
                _running = False
            else:
                # Regular schedule sleep
                sleep_time = int(config.get("sleepInterval", 10))
                if sleep_time >= 60:
                    logger_func(f"> Sleep Engine: Beristirahat {sleep_time//60} menit (Anti-Ban) ...")
                else:
                    logger_func(f"> Sleep Engine: Beristirahat {sleep_time} detik (Anti-Ban) ...")
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
