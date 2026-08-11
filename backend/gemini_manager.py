import json
import logging
import urllib.request
import urllib.error
from typing import List, Optional
from . import settings

logger = logging.getLogger("gemini_manager")

class GeminiManager:
    def __init__(self):
        self.keys: List[str] = []
        self.current_index = 0

    def load_keys(self):
        config = {}
        if settings.SETTINGS_FILE.exists():
            with open(settings.SETTINGS_FILE, "r") as f:
                try:
                    config = json.load(f)
                except:
                    pass
        raw_keys = config.get("geminiApiKeys", "")
        clean_keys = []
        for k in raw_keys.split("\n"):
            cleaned = k.strip().replace(" ✅", "").replace(" ❌", "")
            if cleaned:
                clean_keys.append(cleaned)
        self.keys = clean_keys
        self.current_index = 0

    def get_current_key(self) -> Optional[str]:
        if not self.keys:
            return None
        return self.keys[self.current_index]

    def switch_key(self) -> bool:
        if not self.keys:
            return False
        self.current_index = (self.current_index + 1) % len(self.keys)
        return self.current_index != 0

    def test_key(self, api_key: str) -> bool:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent?key={api_key}"
        payload = json.dumps({"contents": [{"parts": [{"text": "Say 'OK'"}]}]}).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return True
        except Exception as e:
            return False

    def generate_prompt(self, niche: str) -> dict:
        self.load_keys()
        if not self.keys:
            raise ValueError("Tidak ada Gemini API Key yang disetting. Masukkan di Core Settings.")

        prompt_instruction = f"""
Tugasmu adalah membuat master prompt untuk generator gambar (seperti Midjourney/ImageFX) dengan topik: "{niche}".
Format output harus tepat dalam bentuk JSON dengan 4 key berikut, masing-masing berisi 4-5 variasi yang dipisahkan dengan newline (\\n):
{{
    "subject": "Variasi Subjek Utama (wajib diawali instruksi rasio 9:16)\\n...",
    "detail": "Variasi Detail/Pakaian (diawali kata sambung)\\n...",
    "background": "Variasi Latar/Lokasi\\n...",
    "quality": "Variasi Nuansa/Kualitas\\n..."
}}
Buatlah variasi yang menarik, spesifik, estetik, dan relevan dengan topik. Jangan gunakan nomor (1, 2, 3) atau bullet point.
Output HANYA JSON.
"""

        start_index = self.current_index
        while True:
            key = self.get_current_key()
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent?key={key}"
            payload = json.dumps({"contents": [{"parts": [{"text": prompt_instruction}]}]}).encode("utf-8")
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
            
            try:
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                    
                    if text.startswith("```json"):
                        text = text[7:]
                    if text.endswith("```"):
                        text = text[:-3]
                    
                    result = json.loads(text.strip())
                    return result
            except Exception as e:
                logger.error(f"Gemini API Error with key index {self.current_index}: {e}")
                if not self.switch_key():
                    raise ValueError("Semua Gemini API Key gagal atau kehabisan kuota limit.")
                if self.current_index == start_index:
                    raise ValueError("Semua Gemini API Key gagal.")

    def generate_prompt_from_image(self, images_base64: list[str], basic_title: str) -> dict:
        self.load_keys()
        if not self.keys:
            raise ValueError("Tidak ada Gemini API Key yang disetting.")

        parts = []
        
        if images_base64 and len(images_base64) > 0:
            prompt_instruction = f"""
Lihat {len(images_base64)} gambar produk/referensi ini dan judul dasarnya: "{basic_title}".
Tugasmu adalah membuat template Spintax agar hasilnya selalu bervariasi setiap kali di-spin. Gunakan format tradisional Spintax {opsi1|opsi2|opsi3} pada kata atau frasa kunci di semua bagian.

Tugas spesifik:
1. Buat "seo_title": Judul Clickbait Pinterest yang kaya variasi kata kunci dalam format Spintax. Contoh: "{Spill|Bocoran|Rekomendasi} {Meja Kerja|Meja Komputer} {Minimalis|Aesthetic|Modern}".
2. Buat "seo_desc": Deskripsi persuasif (min 2 paragraf) berisi kata kunci, ditulis menggunakan Spintax di setiap kalimat agar teksnya dinamis, dan sertakan maks 5 hashtag di akhir. Contoh: "{Ubah|Dekorasi|Tingkatkan} tampilan {ruang kerja|kamar tidur} Anda dengan...".
3. Buat "master_prompt": SATU prompt bahasa Inggris utuh untuk AI Image Generator (Midjourney/ImageFX) yang mendeskripsikan subjek, detail, background, dan pencahayaan, ditulis menggunakan Spintax pada elemen visual utamanya (DILARANG keras menggunakan flag/parameter seperti --ar 9:16 atau 9:16). Contoh: "{minimalist wooden desk|modern industrial desk} with {black metal frame|solid steel legs} in a {cozy apartment|sunlit home office}...".

Format HANYA JSON:
{{
    "seo_title": "Judul Pinterest",
    "seo_desc": "Deskripsi Pinterest",
    "master_prompt": "..."
}}
"""
            parts.append({"text": prompt_instruction})
            
            for img_b64 in images_base64:
                if not img_b64: continue
                # Clean base64 header if present
                mime_type = "image/jpeg"
                if "," in img_b64:
                    header, img_b64 = img_b64.split(",", 1)
                    if "png" in header: mime_type = "image/png"
                    elif "webp" in header: mime_type = "image/webp"
                
                parts.append({
                    "inline_data": {
                        "mime_type": mime_type,
                        "data": img_b64
                    }
                })
        else:
            prompt_instruction = f"""
Berdasarkan judul dasar produk/topik ini: "{basic_title}".
Tugasmu adalah membuat template Spintax agar hasilnya selalu bervariasi setiap kali di-spin. Gunakan format tradisional Spintax {opsi1|opsi2|opsi3} pada kata atau frasa kunci di semua bagian.

Tugas spesifik:
1. Buat "seo_title": Judul Clickbait Pinterest yang kaya variasi kata kunci dalam format Spintax. Contoh: "{Spill|Bocoran|Rekomendasi} {Meja Kerja|Meja Komputer} {Minimalis|Aesthetic|Modern}".
2. Buat "seo_desc": Deskripsi persuasif (min 2 paragraf) berisi kata kunci, ditulis menggunakan Spintax di setiap kalimat agar teksnya dinamis, dan sertakan maks 5 hashtag di akhir. Contoh: "{Ubah|Dekorasi|Tingkatkan} tampilan {ruang kerja|kamar tidur} Anda dengan...".
3. Buat "master_prompt": SATU prompt bahasa Inggris utuh untuk AI Image Generator (Midjourney/ImageFX) yang mendeskripsikan subjek, detail, background, dan pencahayaan, ditulis menggunakan Spintax pada elemen visual utamanya (DILARANG keras menggunakan flag/parameter seperti --ar 9:16 atau 9:16). Contoh: "{minimalist wooden desk|modern industrial desk} with {black metal frame|solid steel legs} in a {cozy apartment|sunlit home office}...".

Format HANYA JSON:
{{
    "seo_title": "Judul Pinterest",
    "seo_desc": "Deskripsi Pinterest",
    "master_prompt": "..."
}}
"""
            parts = [{"text": prompt_instruction}]

        start_index = self.current_index
        while True:
            key = self.get_current_key()
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent?key={key}"
            
            payload = {
                "contents": [{
                    "parts": parts
                }]
            }
            
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
            
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                    
                    if text.startswith("```json"): text = text[7:]
                    if text.endswith("```"): text = text[:-3]
                    
                    res = json.loads(text.strip())
                    if "master_prompt" in res and isinstance(res["master_prompt"], str):
                        import re
                        # Strip --ar flags and 9:16 ratios
                        cleaned = re.sub(r'--[a-zA-Z0-9]+(\s+[^\s]+)?', '', res["master_prompt"])
                        cleaned = re.sub(r'\b9:16\b', '', cleaned)
                        res["master_prompt"] = cleaned.strip()
                    return res
            except Exception as e:
                logger.error(f"Gemini API Error with key index {self.current_index}: {e}")
                if not self.switch_key():
                    raise ValueError("Semua Gemini API Key gagal.")
                if self.current_index == start_index:
                    raise ValueError("Semua Gemini API Key gagal.")

manager = GeminiManager()
