import asyncio
from playwright.async_api import async_playwright
import os
import json
from pathlib import Path
import sys

# Persist Pinterest sessions in separate dirs per account
PROFILES_BASE_DIR = Path("storage/pinterest_profiles")

async def upload_to_pinterest(image_path: str, title: str, description: str, link: str, account_name: str = "default") -> bool:
    profile_dir = PROFILES_BASE_DIR / account_name
    profile_dir.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )
        page = await browser.new_page()
        try:
            await page.goto("https://www.pinterest.com/pin-creation-tool/")
            await page.wait_for_timeout(3000)
            if "login" in page.url:
                print(f"[{account_name}] Not logged in to Pinterest. Please login manually first via Auth Setup.")
                await browser.close()
                return False
            
            file_input = page.locator("input#storyboard-upload-input")
            await file_input.wait_for(state="attached")
            await file_input.set_input_files(image_path)
            await page.wait_for_timeout(2000)
            
            title_input = page.locator("input#storyboard-selector-title, input[placeholder*='Title'], input[placeholder*='Judul'], input[aria-label*='Title'], input[aria-label*='Judul']").first
            if await title_input.is_visible():
                await title_input.fill(title)
                
            desc_input = page.locator("div[aria-label*='Deskripsikan'], div[aria-label*='Tell everyone'], div[aria-label*='description' i], div[role='textbox'], div[contenteditable='true']").first
            if await desc_input.is_visible():
                await desc_input.fill(description)
                
            link_input = page.locator("input#scrape-view-website-link, input[placeholder*='tautan'], input[placeholder*='link' i], input[aria-label*='link' i], input[aria-label*='tautan']").first
            if await link_input.is_visible():
                await link_input.fill(link)
                
            # Check Publish / Terbitkan / Simpan buttons
            publish_clicked = False
            for btn_name in ["Publish", "Terbitkan", "Simpan", "Save"]:
                btn = page.get_by_role("button", name=btn_name).first
                if await btn.is_visible():
                    await btn.click()
                    publish_clicked = True
                    break
            
            if not publish_clicked:
                # Fallback to red publish button selector
                btn = page.locator("button[data-test-id='board-dropdown-save-button'], button:has-text('Publish'), button:has-text('Terbitkan')").first
                if await btn.is_visible():
                    await btn.click()
                    publish_clicked = True

            await page.wait_for_timeout(8000)
            await browser.close()
            return True
        except Exception as e:
            print(f"Pinterest Upload Error [{account_name}]: {e}")
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
