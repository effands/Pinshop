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

    def generate_prompt_from_image(self, image_base64: str, basic_title: str) -> dict:
        self.load_keys()
        if not self.keys:
            raise ValueError("Tidak ada Gemini API Key yang disetting.")

        parts = []
        
        if image_base64:
            # Clean base64 header if present (e.g., data:image/png;base64,...)
            mime_type = "image/jpeg"
            if "," in image_base64:
                header, image_base64 = image_base64.split(",", 1)
                if "png" in header: mime_type = "image/png"
                elif "webp" in header: mime_type = "image/webp"
            
            prompt_instruction = f"""
Lihat gambar produk/referensi ini dan judul dasarnya: "{basic_title}".
Tugasmu adalah:
1. Buat "seo_title": Judul Clickbait yang dioptimalkan untuk pencarian Pinterest.
2. Buat "seo_desc": Deskripsi panjang (min 2 paragraf) yang persuasif, mengandung kata kunci relevan, dan beberapa hashtag di akhir.
3. Buat master prompt untuk menggenerate ulang gambar ini menjadi lebih estetik di AI Image Generator (Midjourney/ImageFX). Pecah prompt menjadi 4 komponen:
   - "subject": Deskripsi subjek utama (wajib diawali instruksi rasio 9:16).
   - "detail": Detail bentuk/warna/pakaian.
   - "background": Latar belakang atau lokasi yang estetik.
   - "quality": Nuansa, pencahayaan, kualitas render (misal: 4k, photorealistic).

Format HANYA JSON:
{{
    "seo_title": "Judul Pinterest",
    "seo_desc": "Deskripsi Pinterest",
    "subject": "...",
    "detail": "...",
    "background": "...",
    "quality": "..."
}}
"""
            parts = [
                {"text": prompt_instruction},
                {
                    "inline_data": {
                        "mime_type": mime_type,
                        "data": image_base64
                    }
                }
            ]
        else:
            prompt_instruction = f"""
Berdasarkan judul dasar produk/topik ini: "{basic_title}".
Tugasmu adalah:
1. Buat "seo_title": Judul Clickbait yang dioptimalkan untuk pencarian Pinterest.
2. Buat "seo_desc": Deskripsi panjang (min 2 paragraf) yang persuasif, mengandung kata kunci relevan, dan beberapa hashtag di akhir.
3. Buat master prompt untuk menggenerate gambar estetik terkait topik ini di AI Image Generator (Midjourney/ImageFX). Pecah prompt menjadi 4 komponen:
   - "subject": Deskripsi subjek utama (wajib diawali instruksi rasio 9:16).
   - "detail": Detail bentuk/warna/pakaian.
   - "background": Latar belakang atau lokasi yang estetik.
   - "quality": Nuansa, pencahayaan, kualitas render (misal: 4k, photorealistic).

Format HANYA JSON:
{{
    "seo_title": "Judul Pinterest",
    "seo_desc": "Deskripsi Pinterest",
    "subject": "...",
    "detail": "...",
    "background": "...",
    "quality": "..."
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
                    
                    return json.loads(text.strip())
            except Exception as e:
                logger.error(f"Gemini API Error with key index {self.current_index}: {e}")
                if not self.switch_key():
                    raise ValueError("Semua Gemini API Key gagal.")
                if self.current_index == start_index:
                    raise ValueError("Semua Gemini API Key gagal.")

manager = GeminiManager()
