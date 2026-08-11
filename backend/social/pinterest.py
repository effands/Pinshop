import asyncio
from playwright.async_api import async_playwright
import os
import json
from pathlib import Path
import sys

# Persist Pinterest sessions in separate dirs per account
PROFILES_BASE_DIR = Path("storage/pinterest_profiles")

async def upload_to_pinterest(image_path: str, title: str, description: str, link: str, account_name: str = "default", logger_func=None) -> bool:
    def log(msg):
        if logger_func:
            logger_func(msg)
        else:
            print(msg)

    profile_dir = PROFILES_BASE_DIR / account_name
    profile_dir.mkdir(parents=True, exist_ok=True)
    
    log(f"> Membuka browser Pinterest [{account_name}]...")
    async with async_playwright() as p:
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )
        page = await browser.new_page()
        try:
            log("> Mengakses halaman Pin Creation...")
            await page.goto("https://www.pinterest.com/pin-creation-tool/")
            await page.wait_for_timeout(3000)
            if "login" in page.url:
                log(f"[Error] Akun [{account_name}] belum login di Pinterest! Silakan login di tab Auth.")
                await browser.close()
                return False
            
            log(f"> Mengunggah file media ({os.path.basename(image_path)})...")
            file_input = page.locator("input#storyboard-upload-input")
            await file_input.wait_for(state="attached")
            await file_input.set_input_files(image_path)
            await page.wait_for_timeout(2000)
            log(f"> Mengisi Judul: {title[:40]}...")
            title_input = page.locator("input[id*='storyboard-selector-title'], input[placeholder*='Tell everyone'], input[placeholder*='Judul' i], input[placeholder*='title' i]").first
            if await title_input.is_visible():
                await title_input.fill(title)
                
            log("> Mengisi Deskripsi & Hashtag SEO...")
            desc_input = page.locator("[data-test-id='storyboard-description-field-container'] div[contenteditable='true'], div[contenteditable='true'][aria-label*='Describe'], div[contenteditable='true'][aria-label*='Deskripsikan'], div[contenteditable='true'][aria-label*='description' i], textarea[id*='description']").first
            if await desc_input.is_visible():
                await desc_input.fill(description)
                
            if link:
                log(f"> Menyisipkan Tautan Affiliate...")
                link_input = page.locator("input#WebsiteField, input[id*='WebsiteField'], input[placeholder*='Add a link'], input[placeholder*='tautan' i], input[placeholder*='link' i]").first
                if await link_input.is_visible():
                    await link_input.fill(link)
            # Select Pinterest Board
            try:
                board_btn = page.locator("[data-test-id='board-dropdown'], [data-test-id='board-selector'], button[aria-label*='Choose board'], button[aria-label*='Pilih papan'], div[aria-label*='Choose a board']").first
                if await board_btn.is_visible():
                    await board_btn.click()
                    await page.wait_for_timeout(1500)
                    
                    # Click first board in list
                    first_board = page.locator("[data-test-id='board-row'], div[role='option'], li[role='option'], div[data-test-id*='board']").first
                    if await first_board.is_visible():
                        await first_board.click()
                        log("> Papan Pinterest (Board) berhasil dipilih.")
            except Exception as e:
                log(f"[Warning] Gagal memilih Papan: {e}")

            # Toggle AI disclosure label if available
            try:
                ai_switch = page.locator("input[name*='ai-disclosure-switch'], [data-test-id='ai-disclosure-switch'] input, input#pin-creation-ai-disclosure-switch").first
                if await ai_switch.is_visible():
                    is_checked = await ai_switch.is_checked()
                    if not is_checked:
                        log("> Mencentang label 'Mark as AI-Modified' (Dibuat dengan AI)...")
                        await ai_switch.click()
                        await page.wait_for_timeout(1000)

                # Check "This Pin includes an AI-generated person"
                ai_person = page.locator("input[name*='disclosure-person'], input[id*='disclosure-person'], label:has-text('AI-generated person') input, label:has-text('person') input").first
                if not await ai_person.is_visible():
                    ai_person = page.locator("label:has-text('This Pin includes an AI-generated person'), span:has-text('includes an AI-generated person')").first
                
                if await ai_person.is_visible():
                    log("> Mencentang label 'This Pin includes an AI-generated person'...")
                    await ai_person.click()
            except Exception as e:
                log(f"[Warning] Gagal mencentang label AI: {e}")

            log("> Menekan tombol Terbitkan (Publish)...")
            publish_clicked = False
            for btn_name in ["Publish", "Terbitkan", "Simpan", "Save"]:
                btn = page.get_by_role("button", name=btn_name).first
                if await btn.is_visible():
                    await btn.click()
                    publish_clicked = True
                    break
            
            if not publish_clicked:
                btn = page.locator("button[data-test-id='board-dropdown-save-button'], button:has-text('Publish'), button:has-text('Terbitkan')").first
                if await btn.is_visible():
                    await btn.click()
                    publish_clicked = True

            await page.wait_for_timeout(8000)
            await browser.close()
            log(f"✅ Pin Sukses Diterbitkan ke Pinterest!")
            return True
        except Exception as e:
            log(f"[Error] Gagal upload ke Pinterest [{account_name}]: {e}")
            await browser.close()
            return False

async def manual_login(account_name: str = "default"):
    profile_dir = PROFILES_BASE_DIR / account_name
    profile_dir.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )
        page = await browser.new_page()
        await page.goto("https://www.pinterest.com/login/")
        print(f"Waiting for user to login to account {account_name}... Close browser when done.")
        try:
            await page.wait_for_timeout(3600000) 
        except:
            pass
        finally:
            await browser.close()

async def inject_cookies(cookie_json_str: str, account_name: str = "default") -> bool:
    try:
        cookies = json.loads(cookie_json_str)
        if not isinstance(cookies, list):
            return False
            
        cleaned_cookies = []
        for c in cookies:
            cc = {
                "name": c.get("name", ""),
                "value": c.get("value", ""),
                "domain": c.get("domain", ""),
                "path": c.get("path", "/")
            }
            if "secure" in c: cc["secure"] = c["secure"]
            if "httpOnly" in c: cc["httpOnly"] = c["httpOnly"]
            if "expirationDate" in c: cc["expires"] = c["expirationDate"]
            
            ss = str(c.get("sameSite", "")).lower()
            if ss == "no_restriction":
                cc["sameSite"] = "None"
            elif ss == "lax":
                cc["sameSite"] = "Lax"
            elif ss == "strict":
                cc["sameSite"] = "Strict"
                
            cleaned_cookies.append(cc)
            
        profile_dir = PROFILES_BASE_DIR / account_name
        profile_dir.mkdir(parents=True, exist_ok=True)
        async with async_playwright() as p:
            context = await p.chromium.launch_persistent_context(
                user_data_dir=str(profile_dir),
                headless=True
            )
            await context.add_cookies(cleaned_cookies)
            
            # Check validity
            page = await context.new_page()
            await page.goto("https://www.pinterest.com/")
            await page.wait_for_timeout(3000)
            is_valid = "login" not in page.url
            
            await context.close()
        return is_valid
    except Exception as e:
        print(f"Failed to inject cookies [{account_name}]: {e}")
        return False
