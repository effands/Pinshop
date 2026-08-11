"""Affilia — persistent-profile browser sessions for platform automation.

The user logs into the target platform (TikTok, later Shopee) manually, once,
in a real visible Chromium window that we launch. Cookies/localStorage persist
on disk in a per-platform/account profile directory, so later automated runs
reuse that session without ever touching the user's password. Each operation
opens a fresh context, does its work, and closes it — no long-lived shared
browser process to manage/lock across requests.
"""

import asyncio
import json
import logging
import os
import re
import shutil
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from .. import settings

log = logging.getLogger("affilia.social.browser_session")

PROFILES_DIR = settings.STORAGE_DIR / "browser_profiles"
DEFAULT_ACCOUNT = "Akun Utama"

LOGIN_URLS = {
    "tiktok": "https://www.tiktok.com/login/qrcode",
    "shopee": "https://shopee.co.id/buyer/login",
    "flow": "https://labs.google/fx/tools/flow",
    "chatgpt": "https://chatgpt.com/",
}

PROBE_URLS = {
    "tiktok": "https://www.tiktok.com/tiktokstudio/upload",
    "shopee": "https://shopee.co.id/user/purchase",
    "flow": "https://labs.google/fx/tools/flow",
    "chatgpt": "https://chatgpt.com/",
}

_LOGIN_WAIT_SECONDS = 600  # give the user up to 10 minutes to finish logging in
_login_tasks: dict[str, asyncio.Task] = {}
_profile_locks: dict[str, asyncio.Lock] = {}
_TIKTOK_AUTH_COOKIES = {"sessionid", "sessionid_ss", "sid_guard", "sid_tt"}
_CHATGPT_AUTH_COOKIES = {"__Secure-next-auth.session-token", "_puid", "cf_clearance", "oai-did"}


def _has_tiktok_session_cookie(cookies: list[dict]) -> bool:
    return any(cookie.get("name") in _TIKTOK_AUTH_COOKIES and cookie.get("value") for cookie in cookies)


def has_saved_tiktok_session(account: str = DEFAULT_ACCOUNT) -> bool:
    """Fast check on disk without launching Playwright Chromium: does account have session cookies?"""
    import glob
    import sqlite3
    import uuid
    clean_acc = (account or "").strip()
    low = clean_acc.lower()
    if low.startswith("multi_random") or low.startswith("__random__"):
        connected = get_connected_accounts("tiktok")
        return len(connected) > 0

    p_dir = _profile_dir("tiktok", account)
    cookie_paths = glob.glob(str(p_dir / "**" / "Cookies"), recursive=True)
    for c_path in cookie_paths:
        tmp_id = uuid.uuid4().hex[:8]
        tmp_db = p_dir / f"tmp_{tmp_id}.db"
        tmp_wal = p_dir / f"tmp_{tmp_id}.db-wal"
        tmp_shm = p_dir / f"tmp_{tmp_id}.db-shm"
        
        try:
            # Copy all related SQLite files to read the latest WAL data without lock conflicts
            shutil.copy2(c_path, tmp_db)
            if os.path.exists(c_path + "-wal"):
                shutil.copy2(c_path + "-wal", tmp_wal)
            if os.path.exists(c_path + "-shm"):
                shutil.copy2(c_path + "-shm", tmp_shm)
                
            conn = sqlite3.connect(f"file:{str(tmp_db).replace(os.sep, '/')}?mode=ro", uri=True)
            cursor = conn.cursor()
            cursor.execute("SELECT name, value, encrypted_value FROM cookies WHERE host_key LIKE '%tiktok.com%'")
            rows = cursor.fetchall()
            conn.close()
            
            for name, val, enc_val in rows:
                if name in _TIKTOK_AUTH_COOKIES and (val or enc_val):
                    return True
        except Exception:
            pass
        finally:
            for t in (tmp_db, tmp_wal, tmp_shm):
                if t.exists():
                    try: t.unlink(missing_ok=True)
                    except: pass
    return False


def has_saved_chatgpt_session(account: str = DEFAULT_ACCOUNT) -> bool:
    """Fast check on disk: does ChatGPT account have session cookies?"""
    import glob
    import sqlite3
    import uuid
    clean_acc = (account or "").strip()
    low = clean_acc.lower()
    if low.startswith("multi_random") or low.startswith("__random__"):
        connected = get_connected_accounts("chatgpt")
        return len(connected) > 0

    p_dir = _profile_dir("chatgpt", account)
    cookie_paths = glob.glob(str(p_dir / "**" / "Cookies"), recursive=True)
    for c_path in cookie_paths:
        tmp_id = uuid.uuid4().hex[:8]
        tmp_db = p_dir / f"tmp_{tmp_id}.db"
        tmp_wal = p_dir / f"tmp_{tmp_id}.db-wal"
        tmp_shm = p_dir / f"tmp_{tmp_id}.db-shm"
        
        try:
            # Copy all related SQLite files to read the latest WAL data without lock conflicts
            shutil.copy2(c_path, tmp_db)
            if os.path.exists(c_path + "-wal"):
                shutil.copy2(c_path + "-wal", tmp_wal)
            if os.path.exists(c_path + "-shm"):
                shutil.copy2(c_path + "-shm", tmp_shm)
                
            conn = sqlite3.connect(f"file:{str(tmp_db).replace(os.sep, '/')}?mode=ro", uri=True)
            cursor = conn.cursor()
            cursor.execute("SELECT name, value, encrypted_value FROM cookies WHERE host_key LIKE '%chatgpt.com%' OR host_key LIKE '%openai.com%'")
            rows = cursor.fetchall()
            conn.close()
            
            for name, val, enc_val in rows:
                if name in _CHATGPT_AUTH_COOKIES and (val or enc_val):
                    return True
        except Exception:
            pass
        finally:
            for t in (tmp_db, tmp_wal, tmp_shm):
                if t.exists():
                    try: t.unlink(missing_ok=True)
                    except: pass
    return False


def _profile_dir(platform: str, account: str):
    import re
    safe_name = re.sub(r'[\/:*?"<>|\s]', '_', (account or "").strip())
    if not safe_name:
        safe_name = "default"
    d = PROFILES_DIR / platform / safe_name
    old_dir = PROFILES_DIR / platform / account
    if old_dir != d and old_dir.exists() and not d.exists():
        try:
            shutil.move(str(old_dir), str(d))
        except Exception:
            pass
    d.mkdir(parents=True, exist_ok=True)
    return d


@asynccontextmanager
async def profile_operation(platform: str, account: str, timeout: float = 3.0):
    """Enforce sequential access for the exact same account profile on disk to prevent
    Chromium 'Opening in existing browser session' profile lock collisions, while allowing
    different accounts to execute concurrently in parallel."""
    key = f"{platform}:{account}"
    if key not in _profile_locks:
        _profile_locks[key] = asyncio.Lock()
    lock = _profile_locks[key]
    try:
        lock_loop = lock._loop if hasattr(lock, "_loop") else None
        curr_loop = asyncio.get_running_loop()
        if lock_loop is not None and lock_loop != curr_loop:
            lock = asyncio.Lock()
            _profile_locks[key] = lock
    except Exception:
        lock = asyncio.Lock()
        _profile_locks[key] = lock

    acquired = False
    try:
        if lock.locked():
            try:
                await asyncio.wait_for(lock.acquire(), timeout=timeout)
                acquired = True
            except asyncio.TimeoutError:
                log.info("Profile lock '%s' busy, enabling temp clone fallback for parallel run...", account)
                acquired = False
        else:
            await lock.acquire()
            acquired = True
        yield
    finally:
        if acquired:
            try:
                lock.release()
            except Exception:
                pass


def list_accounts(platform: str) -> list[dict]:
    return list_accounts_detailed(platform)


def create_account(platform: str, name: str) -> bool:
    name = name.strip()
    if not name:
        return False
    username = ""
    if " - @" in name:
        parts = name.split(" - @", 1)
        account_name = parts[0].strip()
        username = "@" + parts[1].strip()
    elif " @" in name:
        parts = name.rsplit(" @", 1)
        account_name = parts[0].strip()
        username = "@" + parts[1].strip()
    else:
        account_name = name

    _profile_dir(platform, account_name)
    if username:
        save_account_meta(platform, account_name, {"username": username})
    return True


def delete_account(platform: str, name: str) -> bool:
    target_names = {name, name.strip().replace(" ", "_"), name.strip().replace("_", " ")}
    deleted_any = False

    for acc_name in target_names:
        if not acc_name:
            continue
        p_dir = PROFILES_DIR / platform / acc_name
        if not p_dir.exists():
            continue

        # Forcefully attempt deletion with retries
        for attempt in range(3):
            try:
                shutil.rmtree(p_dir, ignore_errors=False)
                break
            except Exception:
                try:
                    for root, dirs, files in os.walk(p_dir, topdown=False):
                        for f in files:
                            try:
                                (Path(root) / f).unlink(missing_ok=True)
                            except Exception:
                                pass
                        for dr in dirs:
                            try:
                                (Path(root) / dr).rmdir()
                            except Exception:
                                pass
                    p_dir.rmdir()
                except Exception:
                    pass

        if not p_dir.exists():
            deleted_any = True
        else:
            # Fallback for Windows file lock: rename directory so it won't show up in list_accounts_detailed
            try:
                import time
                trash_dir = PROFILES_DIR / platform / f"_deleted_{acc_name}_{int(time.time())}"
                p_dir.rename(trash_dir)
                shutil.rmtree(trash_dir, ignore_errors=True)
                deleted_any = True
            except Exception as e:
                log.warning("Gagal menghapus folder profil %s: %s", p_dir, e)

    return deleted_any


async def _launch_context(platform: str, account: str, headless: bool):
    from playwright.async_api import async_playwright
    import uuid

    mode = settings.get_same_account_concurrency_mode()
    p_dir = _profile_dir(platform, account)
    temp_dir = None

    lock_file = p_dir / "SingletonLock"
    lock_file_win = p_dir / "lockfile"
    if lock_file.exists() or lock_file_win.exists():
        temp_name = f"_{p_dir.name}_temp_{uuid.uuid4().hex[:6]}"
        temp_dir = PROFILES_DIR / platform / temp_name
        try:
            shutil.copytree(p_dir, temp_dir, ignore=shutil.ignore_patterns("Singleton*", "DevToolsActivePort", "lockfile"))
            p_dir = temp_dir
            log.info("Profil '%s' sedang aktif, meng-kloning profil ke folder temporer '%s' agar bisa dibuka serentak...", account, temp_name)
        except Exception as e:
            log.warning("Temp clone fallback: %s", e)
            p_dir = _profile_dir(platform, account)

    for lock_name in ["SingletonLock", "SingletonSocket", "SingletonCookie", "DevToolsActivePort", "lockfile"]:
        l_file = p_dir / lock_name
        if l_file.exists():
            try:
                if l_file.is_dir():
                    shutil.rmtree(l_file, ignore_errors=True)
                else:
                    l_file.unlink(missing_ok=True)
            except Exception:
                pass

    # Wipe session restore files across all profile directories so Chromium never restores extra tabs
    try:
        if PROFILES_DIR.exists():
            for p_sub in PROFILES_DIR.glob("**/*"):
                if p_sub.is_dir() and p_sub.name == "Sessions":
                    shutil.rmtree(p_sub, ignore_errors=True)
                elif p_sub.is_file() and p_sub.name in ("Current Session", "Current Tabs", "Last Session", "Last Tabs"):
                    p_sub.unlink(missing_ok=True)
    except Exception:
        pass

    playwright = None
    bridge = None
    context = None
    try:
        playwright = await async_playwright().start()
        meta = get_account_meta(platform, account)
        account_proxy = (meta.get("proxy") or "").strip()
        effective_proxy_url = account_proxy if account_proxy else settings.get_tiktok_proxy()
        if account_proxy:
            log.info("Menggunakan Proxy Spesifik Akun '%s': %s", account, account_proxy)
        proxy_config = settings.parse_playwright_proxy(effective_proxy_url)
        from ..proxy_bridge import start_proxy_bridge_if_needed
        effective_proxy, bridge = await start_proxy_bridge_if_needed(proxy_config)

        launch_kwargs = {
            "user_data_dir": str(p_dir),
            "headless": headless,
            "no_viewport": True,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--restore-last-session=0",
                "--no-first-run",
                "--no-service-autorun",
                "--password-store=basic",
            ],
        }
        if effective_proxy:
            launch_kwargs["proxy"] = effective_proxy
        context = await playwright.chromium.launch_persistent_context(**launch_kwargs)

        # Chromium may finish restoring stale tabs just after launch.  Clean that
        # startup state once, but never keep a permanent page listener: TikTok can
        # legitimately replace its active tab during upload and killing that new
        # page closes the whole visible browser session.
        await asyncio.sleep(0.4)
        main_page = context.pages[0] if context.pages else await context.new_page()
        for p in list(context.pages):
            if p != main_page:
                try:
                    await p.close()
                except Exception:
                    pass

        orig_close = context.close
        async def _close_with_cleanup():
            try:
                await orig_close()
            finally:
                if bridge:
                    await bridge.stop()
                if temp_dir and temp_dir.exists():
                    shutil.rmtree(temp_dir, ignore_errors=True)

        context.close = _close_with_cleanup
        return playwright, context
    except BaseException:
        if context:
            try:
                await asyncio.wait_for(context.close(), timeout=4.0)
            except BaseException:
                pass
        if bridge:
            try:
                await bridge.stop()
            except BaseException:
                pass
        if playwright:
            try:
                await asyncio.wait_for(playwright.stop(), timeout=4.0)
            except BaseException:
                pass
        if temp_dir and temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)
        raise


async def safe_close_session(context, playwright=None, timeout: float = 4.0):
    """Safely close Playwright context and stop driver with timeout to prevent Windows process hangs."""
    if context:
        try:
            pages = list(context.pages)
            if len(pages) > 1:
                for p in pages[1:]:
                    try:
                        await p.close()
                    except Exception:
                        pass
        except Exception:
            pass
        try:
            await asyncio.wait_for(context.close(), timeout=timeout)
        except Exception:
            pass
    if playwright:
        try:
            await asyncio.wait_for(playwright.stop(), timeout=timeout)
        except Exception:
            pass


def is_login_in_progress(platform: str, account: str = DEFAULT_ACCOUNT) -> bool:
    task = _login_tasks.get(f"{platform}:{account}")
    return task is not None and not task.done()


async def cancel_login_tasks() -> int:
    """Cancel only login browsers launched and owned by Affilia."""
    tasks = [task for task in _login_tasks.values() if not task.done()]
    for task in tasks:
        task.cancel()
    if tasks:
        try:
            await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=0.5)
        except asyncio.TimeoutError:
            pass
    for key, task in list(_login_tasks.items()):
        if task.done():
            _login_tasks.pop(key, None)
    return len(tasks)


async def login_account(platform: str, account: str = DEFAULT_ACCOUNT, target_url: str = None) -> None:
    """Launches non-headless browser session and waits for manual login in the
    background; the HTTP endpoint that triggers this returns immediately."""
    key = f"{platform}:{account}"
    if is_login_in_progress(platform, account):
        return

    async def _do_login():
        login_url = target_url or LOGIN_URLS.get(platform)
        if not login_url:
            log.error("No login URL configured for platform %s", platform)
            return
        playwright = None
        context = None
        try:
            playwright, context = await _launch_context(platform, account, headless=False)
            page = context.pages[0] if context.pages else await context.new_page()
            try:
                await page.goto(login_url, wait_until="commit", timeout=60000)
            except Exception as nav_err:
                log.warning("Notice navigasi login %s (%s): %s", platform, account, nav_err)
            log.info("Waiting for manual login on %s (account=%s)...", platform, account)

            elapsed = 0
            poll_interval = 2
            max_wait = 36000 if target_url else _LOGIN_WAIT_SECONDS
            while elapsed < max_wait:
                await asyncio.sleep(poll_interval)
                elapsed += poll_interval
                try:
                    if page.is_closed():
                        log.info("User closed login browser window for %s (account=%s).", platform, account)
                        break

                    # Continuously capture & save session cookies and @username while browser is open
                    try:
                        if platform == "tiktok":
                            cookies = await context.cookies("https://www.tiktok.com")
                            curr_url = page.url.lower()
                            try:
                                info = await page.evaluate("""() => {
                                    let res = { username: "", display_name: "", avatar: "", followers: "" };
                                    
                                    let myUsername = null;
                                    const profileLink = document.querySelector('a[data-e2e="nav-profile"]');
                                    if (profileLink) {
                                        const match = profileLink.getAttribute('href')?.match(/@([a-zA-Z0-9_.-]+)/);
                                        if (match) myUsername = match[1];
                                    }
                                    
                                    try {
                                        const data = document.getElementById('__UNIVERSAL_DATA_FOR_REHYDRATION__');
                                        if (data) {
                                            const parsed = JSON.parse(data.textContent);
                                            const user = parsed.__DEFAULT_SCOPE__?.['webapp.user']?.userInfo?.user;
                                            const stats = parsed.__DEFAULT_SCOPE__?.['webapp.user']?.userInfo?.stats;
                                            if (user && user.uniqueId) {
                                                if (!myUsername || user.uniqueId === myUsername) {
                                                    res.username = user.uniqueId;
                                                    res.display_name = user.nickname || "";
                                                    res.avatar = user.avatarLarger || user.avatarMedium || user.avatarThumb || "";
                                                    if (stats && stats.followerCount !== undefined) res.followers = stats.followerCount.toString();
                                                    return res;
                                                }
                                            }
                                        }
                                    } catch (e) {}
                                    
                                    if (window.location.pathname.includes('/@')) {
                                        const dNameEl = document.querySelector('h1[data-e2e="user-title"]');
                                        const uNameEl = document.querySelector('h2[data-e2e="user-subtitle"]');
                                        let profileUsername = uNameEl ? uNameEl.innerText.trim() : "";
                                        
                                        if (profileUsername && myUsername && profileUsername !== myUsername) {
                                            return res;
                                        }
                                        
                                        if (dNameEl) res.display_name = dNameEl.innerText.trim();
                                        res.username = profileUsername || myUsername || "";
                                        const avatarEl = document.querySelector('span[data-e2e="user-avatar"] img, img[class*="ImgAvatar"]');
                                        if (avatarEl) res.avatar = avatarEl.src;
                                    } else if (myUsername) {
                                        res.username = myUsername;
                                    }
                                    return res;
                                }""")
                                if info and info.get("username"):
                                    meta = get_account_meta(platform, account)
                                    updates = {}
                                    for k in ["username", "display_name", "avatar", "followers"]:
                                        if info.get(k) and str(info.get(k)) != str(meta.get(k)):
                                            updates[k] = info.get(k)
                                    if updates:
                                        save_account_meta(platform, account, updates)
                            except Exception:
                                pass

                            if _has_tiktok_session_cookie(cookies) and "login" not in curr_url and "passport" not in curr_url and "qrcode" not in curr_url:
                                if not target_url:
                                    try:
                                        profile_link = await page.query_selector('a[data-e2e="nav-profile"], a[href^="/@"]')
                                        if profile_link:
                                            href = await profile_link.get_attribute("href")
                                            if href and "/@" in href:
                                                await page.goto(f"https://www.tiktok.com{href}", wait_until="networkidle")
                                                await asyncio.sleep(2.0)
                                                d_name = await page.evaluate("() => { const el = document.querySelector('h1[data-e2e=\"user-title\"]'); return el ? el.innerText.trim() : ''; }")
                                                u_name = await page.evaluate("() => { const el = document.querySelector('h2[data-e2e=\"user-subtitle\"]'); return el ? el.innerText.trim() : ''; }")
                                                avatar = await page.evaluate("() => { const el = document.querySelector('span[data-e2e=\"user-avatar\"] img, img[class*=\"ImgAvatar\"]'); return el ? el.src : ''; }")
                                                
                                                meta = get_account_meta(platform, account)
                                                updates = {}
                                                if u_name and u_name != meta.get("username"): updates["username"] = u_name
                                                if d_name and d_name != meta.get("display_name"): updates["display_name"] = d_name
                                                if avatar and avatar != meta.get("avatar"): updates["avatar"] = avatar
                                                if updates:
                                                    save_account_meta(platform, account, updates)
                                    except Exception:
                                        pass
                                    await asyncio.sleep(1.0)
                                    log.info("TikTok login confirmed for %s, auto-closing browser window.", account)
                                    break
                        elif platform == "shopee":
                            cookies = await context.cookies("https://shopee.co.id")
                            if any(c.get("name") in {"SPC_EC", "shopee_token"} for c in cookies):
                                username = await _try_extract_username(page)
                                if username:
                                    save_account_meta(platform, account, {"username": username})
                        elif platform == "chatgpt":
                            cookies = await context.cookies(["https://chatgpt.com", "https://openai.com"])
                            curr_url = page.url.lower()
                            has_gpt_cookie = any(
                                c.get("name") in {"__Secure-next-auth.session-token", "_puid", "oai-did"}
                                for c in cookies
                            )
                            has_prompt_box = False
                            try:
                                prompt_el = await page.query_selector("#prompt-textarea, textarea[data-id]")
                                if prompt_el:
                                    has_prompt_box = True
                            except Exception:
                                pass

                            if (has_gpt_cookie or has_prompt_box) and "auth" not in curr_url and "login" not in curr_url:
                                try:
                                    user_el = await page.query_selector('[data-testid="profile-button"]')
                                    if user_el:
                                        uname = (await user_el.inner_text()).strip()
                                        if uname:
                                            save_account_meta("chatgpt", account, {"username": uname})
                                except Exception:
                                    pass
                                if not target_url:
                                    await asyncio.sleep(2.0)
                                    log.info("ChatGPT login confirmed for %s, auto-closing browser window.", account)
                                    break
                    except Exception:
                        pass
                except Exception:
                    break
        except Exception:
            log.exception("Login browser session failed for %s", platform)
        finally:
            if context:
                await context.close()
            if playwright:
                await playwright.stop()

    async def _run():
        if sys.platform == "win32":
            loop = asyncio.get_running_loop()
            def _worker():
                policy = asyncio.WindowsProactorEventLoopPolicy()
                sub_loop = policy.new_event_loop()
                asyncio.set_event_loop(sub_loop)
                try:
                    sub_loop.run_until_complete(_do_login())
                finally:
                    sub_loop.close()
            await loop.run_in_executor(None, _worker)
        else:
            await _do_login()

    _login_tasks[key] = asyncio.create_task(_run())


open_login_browser = login_account


def save_account_meta(platform: str, account: str, meta: dict):
    p_dir = _profile_dir(platform, account)
    meta_file = p_dir / "affilia_meta.json"
    existing = {}
    if meta_file.exists():
        try:
            existing = json.loads(meta_file.read_text(encoding="utf-8"))
        except Exception:
            pass
    existing.update(meta)
    try:
        meta_file.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    except Exception:
        pass


def get_account_meta(platform: str, account: str) -> dict:
    p_dir = _profile_dir(platform, account)
    for path in [p_dir / "affilia_meta.json", PROFILES_DIR / platform / account / "affilia_meta.json"]:
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                pass
    return {}


def list_accounts_detailed(platform: str) -> list[dict]:
    base = PROFILES_DIR / platform
    base.mkdir(parents=True, exist_ok=True)
    raw_names = [
        d.name for d in base.iterdir()
        if d.is_dir()
        and not d.name.startswith("_")
        and not d.name.startswith(".")
        and not d.name.lower().startswith("multi_random")
        and not d.name.lower().startswith("multi random")
        and not d.name.lower().startswith("__random__")
        and not d.name.lower().startswith("test_login")
        and not d.name.lower().startswith("test login")
        and not d.name.lower().startswith("test_job")
    ]
    clean_set = set()
    for name in raw_names:
        clean_set.add(name.replace("_", " "))
    names = sorted(list(clean_set))
    if not names:
        _profile_dir(platform, DEFAULT_ACCOUNT)
        names = [DEFAULT_ACCOUNT]

    result = []
    for name in names:
        meta = get_account_meta(platform, name)
        username = meta.get("username", "").strip()
        email = meta.get("email", "").strip()
        password = meta.get("password", "")
        proxy = meta.get("proxy", "").strip()
        followers = meta.get("followers", "")
        if username:
            u_clean = username if username.startswith("@") else f"@{username}"
            label = f"{name} - {u_clean}"
        else:
            label = name
            
        logged_in = False
        if platform == "tiktok":
            logged_in = has_saved_tiktok_session(name)
        elif platform == "chatgpt":
            logged_in = has_saved_chatgpt_session(name)
            
        result.append({
            "id": name,
            "name": name,
            "username": username,
            "followers": followers,
            "email": email,
            "password": password,
            "proxy": proxy,
            "label": label,
            "logged_in": logged_in
        })
    return result


def get_connected_accounts(platform: str = "tiktok") -> list[str]:
    """Returns a list of account names that have active saved session cookies on disk."""
    all_accs = [a["name"] for a in list_accounts_detailed(platform)]
    connected = []
    for acc in all_accs:
        if platform == "tiktok" and has_saved_tiktok_session(acc):
            connected.append(acc)
        elif platform == "chatgpt" and has_saved_chatgpt_session(acc):
            connected.append(acc)
    return connected if connected else ([all_accs[0]] if all_accs else [DEFAULT_ACCOUNT])


def resolve_account(
    account: str,
    platform: str = "tiktok",
    item_index: int = 0,
    exclude_accounts: set[str] | list[str] | None = None,
) -> str:
    """If account is 'multi_random' or 'multi_random:Acc1,Acc2', returns a connected account name
    rotated round-robin within the pool. Excludes active running accounts if provided."""
    clean_acc = (account or "").strip()
    if not clean_acc:
        return DEFAULT_ACCOUNT

    exclude = set(exclude_accounts or [])
    low = clean_acc.lower()
    if low.startswith("multi_random:") or low.startswith("__random__:") or low.startswith("multi_random_profile:"):
        _, raw_subset = clean_acc.split(":", 1)
        selected_names = [s.strip() for s in raw_subset.split(",") if s.strip()]
        if selected_names:
            connected_subset = []
            for sname in selected_names:
                if platform == "tiktok" and has_saved_tiktok_session(sname):
                    connected_subset.append(sname)
                elif platform == "chatgpt" and has_saved_chatgpt_session(sname):
                    connected_subset.append(sname)
                else:
                    all_existing = [a["name"] for a in list_accounts_detailed(platform)]
                    if sname in all_existing:
                        connected_subset.append(sname)
            target_pool = connected_subset if connected_subset else selected_names
            non_active_pool = [a for a in target_pool if a not in exclude]
            use_pool = non_active_pool if non_active_pool else target_pool
            idx = item_index % len(use_pool)
            return use_pool[idx]

    if low in {"multi_random", "__random__", "multi_random_profile"} or low.startswith("multi_random") or low.startswith("__random__"):
        connected = get_connected_accounts(platform)
        if not connected:
            return DEFAULT_ACCOUNT
        non_active_pool = [a for a in connected if a not in exclude]
        use_pool = non_active_pool if non_active_pool else connected
        idx = item_index % len(use_pool)
        return use_pool[idx]

    return clean_acc or DEFAULT_ACCOUNT


async def _try_extract_profile_data(page) -> dict:
    try:
        username = await page.evaluate("""() => {
            const avatar = document.querySelector('[data-e2e="user-avatar"]') || document.querySelector('a[href*="/@"]');
            if (avatar) {
                const href = avatar.getAttribute('href') || '';
                const match = href.match(/@([a-zA-Z0-9_.-]+)/);
                if (match) return match[1];
            }
            const link = document.querySelector('a[href^="/@"]');
            if (link) {
                const href = link.getAttribute('href') || '';
                const match = href.match(/@([a-zA-Z0-9_.-]+)/);
                if (match) return match[1];
            }
            return '';
        }""")
        username = username.strip() if username else ""
        if not username:
            return {}

        try:
            await page.goto(f"https://www.tiktok.com/@{username}", timeout=20000)
            try:
                # Wait for the stat element to appear in DOM, but don't fail if it doesn't
                await page.wait_for_selector('[data-e2e="followers-stat"], [title="Followers"]', timeout=3000)
            except:
                await page.wait_for_timeout(1000)
                
            data = await page.evaluate("""() => {
                let res = { followers: "", display_name: "" };
                
                try {
                    const data = document.getElementById('__UNIVERSAL_DATA_FOR_REHYDRATION__');
                    if (data) {
                        const parsed = JSON.parse(data.textContent);
                        const scope = parsed.__DEFAULT_SCOPE__ || {};
                        const webappUser = scope['webapp.user-detail'] || scope['webapp.user'] || {};
                        const user = webappUser.userInfo?.user;
                        const stats = webappUser.userInfo?.stats;
                        
                        if (user) {
                            res.display_name = user.nickname || "";
                        }
                        if (stats && stats.followerCount !== undefined) {
                            res.followers = stats.followerCount.toString();
                        }
                        if (res.followers) return res;
                    }
                } catch (e) {}

                const getNum = () => {
                    const selectors = [
                        '[data-e2e="followers-stat"]',
                        '[title="Followers"]',
                        '[data-e2e="followers-count"]'
                    ];
                    for (let sel of selectors) {
                        const el = document.querySelector(sel);
                        if (el) {
                            let text = el.textContent.trim().replace(/,/g, '');
                            let match = text.match(/([0-9.]+)[KkMm]?/);
                            if (match) {
                                let numStr = match[0].toUpperCase();
                                if (numStr.endsWith('K')) return String(parseFloat(numStr) * 1000);
                                if (numStr.endsWith('M')) return String(parseFloat(numStr) * 1000000);
                                return match[1];
                            }
                        }
                    }
                    return "";
                };
                res.followers = res.followers || getNum();
                const titleEl = document.querySelector('[data-e2e="user-title"], h1[data-e2e="user-title"]');
                res.display_name = res.display_name || (titleEl ? titleEl.textContent.trim() : "");
                
                return res;
            }""")
            return {
                "username": username,
                "followers": data.get("followers", ""),
                "display_name": data.get("display_name", "")
            }
        except Exception:
            return {"username": username}

    except Exception:
        return {}


async def check_session(
    platform: str, account: str = DEFAULT_ACCOUNT, *, lock_profile: bool = True, fast_disk_only: bool = True
) -> bool:
    """Checks if there is a usable saved session for this account.
    By default uses fast disk check (0.005s) to avoid launching Playwright for UI status checks.
    """
    if platform == "tiktok":
        if has_saved_tiktok_session(account):
            return True
        if fast_disk_only:
            return False
    elif platform == "chatgpt":
        if has_saved_chatgpt_session(account):
            return True
        if fast_disk_only:
            return False

    if lock_profile:
        async with profile_operation(platform, account):
            return await check_session(platform, account, lock_profile=False, fast_disk_only=False)

    probe_url = PROBE_URLS.get(platform)
    if not probe_url:
        return False
    playwright = None
    context = None
    try:
        playwright, context = await _launch_context(platform, account, headless=True)
        page = context.pages[0] if context.pages else await context.new_page()
        if platform == "tiktok":
            cookies = await context.cookies("https://www.tiktok.com")

        try:
            await page.goto(probe_url, wait_until="domcontentloaded", timeout=25000)
            await page.wait_for_timeout(1000)
        except Exception as e:
            log.debug("Notice saat probe navigasi %s (%s): %s", platform, account, e)

        if "login" in page.url.lower():
            return False
        if platform == "tiktok":
            cookies = await context.cookies("https://www.tiktok.com")
            is_conn = _has_tiktok_session_cookie(cookies)
            if is_conn:
                meta = await _try_extract_profile_data(page)
                if meta and meta.get("username"):
                    save_account_meta(platform, account, meta)
            return is_conn
        return True
    except Exception as e:
        log.warning("Session check tidak terhubung untuk %s (%s): %s", platform, account, e)
        return False
    finally:
        if context:
            await context.close()
        if playwright:
            await playwright.stop()


async def get_context(platform: str, account: str = DEFAULT_ACCOUNT, headless: bool = True):
    """Caller is responsible for closing the returned (playwright, context) pair."""
    return await _launch_context(platform, account, headless)


def cleanup_profile_junk_cache(platform: str = "", account: str = "") -> dict:
    """Safely purges Chromium temporary media cache, code cache, GPUCache, and
    ServiceWorker/CacheStorage folders from browser profiles without removing user
    session cookies, localStorage, or login state.
    """
    targets = []
    if platform and account:
        pdir = _profile_dir(platform, account)
        targets.append(pdir)
    else:
        if PROFILES_DIR.exists():
            targets = [p for p in PROFILES_DIR.glob("*/*") if p.is_dir()]

    junk_folder_names = {"Cache", "Code Cache", "GPUCache", "CacheStorage", "ScriptCache", "Cache_Data"}
    freed_bytes = 0
    cleaned_count = 0

    for pdir in targets:
        default_dir = pdir / "Default"
        if not default_dir.exists():
            continue
        for item in list(default_dir.rglob("*")):
            if item.is_dir() and item.name in junk_folder_names:
                try:
                    sub_freed = 0
                    for f in list(item.rglob("*")):
                        if f.is_file():
                            sub_freed += f.stat().st_size
                    shutil.rmtree(str(item), ignore_errors=True)
                    freed_bytes += sub_freed
                    cleaned_count += 1
                except Exception as e:
                    log.warning("Gagal menghapus cache folder %s: %s", item, e)

    freed_mb = round(freed_bytes / (1024 * 1024), 2)
    log.info("Pembersihan cache profil browser: membebaskan %.2f MB dari %d folder cache", freed_mb, cleaned_count)
    return {
        "freed_bytes": freed_bytes,
        "freed_mb": freed_mb,
        "cleaned_folders": cleaned_count,
    }

async def sync_account_info(platform: str, account: str) -> dict:
    if platform != "tiktok":
        return get_account_meta(platform, account)
    
    meta = get_account_meta(platform, account)
    known_username = meta.get("username", "").strip()
    
    playwright = None
    context = None
    try:
        playwright, context = await _launch_context(platform, account, headless=True)
        page = context.pages[0] if context.pages else await context.new_page()
        
        profile_url = None
        if known_username:
            profile_url = f"https://www.tiktok.com/@{known_username}"
        else:
            await page.goto("https://www.tiktok.com/", wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2.0)
            profile_url = await page.evaluate("""() => {
                const link = document.querySelector('a[data-e2e="nav-profile"]');
                return link ? link.href : null;
            }""")
        
        if profile_url and "/@" in profile_url:
            await page.goto(profile_url, wait_until="domcontentloaded", timeout=30000)
            try:
                await page.wait_for_selector('[data-e2e="followers-stat"], [title="Followers"], [data-e2e="followers-count"]', timeout=3000)
            except:
                await asyncio.sleep(2.0)
            
        info = await page.evaluate("""() => {
            let res = { username: "", display_name: "", avatar: "", followers: "" };
            
            let myUsername = null;
            const profileLink = document.querySelector('a[data-e2e="nav-profile"]');
            if (profileLink) {
                const match = profileLink.getAttribute('href')?.match(/@([a-zA-Z0-9_.-]+)/);
                if (match) myUsername = match[1];
            }
            
            try {
                const data = document.getElementById('__UNIVERSAL_DATA_FOR_REHYDRATION__');
                if (data) {
                    const parsed = JSON.parse(data.textContent);
                    const scope = parsed.__DEFAULT_SCOPE__ || {};
                    const webappUser = scope['webapp.user-detail'] || scope['webapp.user'] || {};
                    const user = webappUser.userInfo?.user;
                    const stats = webappUser.userInfo?.stats;
                    
                    if (user && user.uniqueId) {
                        if (!myUsername || user.uniqueId === myUsername) {
                            res.username = user.uniqueId;
                            res.display_name = user.nickname || "";
                            res.avatar = user.avatarLarger || user.avatarMedium || user.avatarThumb || "";
                            if (stats && stats.followerCount !== undefined) res.followers = stats.followerCount.toString();
                            if (res.followers) return res; // if followers found via JSON, return early
                        }
                    }
                }
            } catch (e) {}
            
            if (window.location.pathname.includes('/@')) {
                const dNameEl = document.querySelector('h1[data-e2e="user-title"]');
                const uNameEl = document.querySelector('h2[data-e2e="user-subtitle"]');
                let profileUsername = uNameEl ? uNameEl.innerText.trim() : "";
                
                if (profileUsername && myUsername && profileUsername !== myUsername) {
                    return res;
                }
                
                if (dNameEl) res.display_name = dNameEl.innerText.trim();
                res.username = profileUsername || myUsername || "";
                const avatarEl = document.querySelector('span[data-e2e="user-avatar"] img, img[class*="ImgAvatar"]');
                if (avatarEl) res.avatar = avatarEl.src;
                
                // Robust Followers Extractor
                const getNum = () => {
                    const selectors = [
                        '[data-e2e="followers-stat"]',
                        '[title="Followers"]',
                        '[data-e2e="followers-count"]'
                    ];
                    for (let sel of selectors) {
                        const el = document.querySelector(sel);
                        if (el) {
                            let text = el.textContent.trim().replace(/,/g, '');
                            let match = text.match(/([0-9.]+)[KkMm]?/);
                            if (match) {
                                let numStr = match[0].toUpperCase();
                                if (numStr.endsWith('K')) return String(parseFloat(numStr) * 1000);
                                if (numStr.endsWith('M')) return String(parseFloat(numStr) * 1000000);
                                return match[1];
                            }
                        }
                    }
                    return "";
                };
                res.followers = getNum();
                
            } else if (myUsername) {
                res.username = myUsername;
            }
            return res;
        }""")
        
        meta = get_account_meta(platform, account)
        if info:
            if not info.get("username") and known_username:
                info["username"] = known_username
                
            if info.get("username"):
                updates = {}
                for k in ["username", "display_name", "avatar", "followers"]:
                    if info.get(k) and str(info.get(k)) != str(meta.get(k)):
                        updates[k] = info.get(k)
                if updates:
                    save_account_meta(platform, account, updates)
                meta = get_account_meta(platform, account)
                
        return meta
    except Exception as e:
        log.error("Failed to sync account %s: %s", account, e)
        return get_account_meta(platform, account)
    finally:
        if context: await context.close()
        if playwright: await playwright.stop()
