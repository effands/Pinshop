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
        for model in ["gemini-3.6-flash", "gemini-3.5-flash"]:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
            payload = json.dumps({"contents": [{"parts": [{"text": "Say 'OK'"}]}]}).encode("utf-8")
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    return True
            except Exception as e:
                logger.warning(f"Key test failed for model {model}: {e}")
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
            success = False
            result = None
            for model in ["gemini-3.6-flash", "gemini-3.5-flash"]:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
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
                        success = True
                        break
                except Exception as e:
                    logger.warning(f"Gemini API Key index {self.current_index} failed with model {model}: {e}. Trying next key...")
            
            if success:
                return result
                
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

WAJIB DAN MUTLAK: Seluruh teks output (seo_title, seo_desc, master_prompt) HARUS ditulis menggunakan format tradisional Spintax {{opsi1|opsi2|opsi3}} pada kata atau frasa kunci di dalamnya agar hasilnya selalu bervariasi setiap kali di-spin. Dilarang keras menghasilkan teks polos tanpa Spintax!

Tugas spesifik:
1. Buat "seo_title": Judul Pinterest SEO-LSI Clickbait yang PANJANG (antara 70 hingga 100 karakter). Harus sangat kaya akan kata kunci pencarian utama Pinterest yang relevan dengan topik, digabung dengan hook emosional/clickbait.
DILARANG KERAS DAN DIHARAMKAN menggunakan kata "shopee", "racun", atau nama brand e-commerce lainnya di dalam judul. Orang di Pinterest mencari inspirasi desain, ide, dan estetika, bukan brand marketplace.
Fokus pada kata kunci LSI pencarian Pinterest seperti: ide dekorasi, inspirasi setup, desain interior, gaya minimalis, estetik, modern scandinavian, dll.
Wajib menggunakan format Spintax yang padat.
Contoh format ideal: "{{Inspirasi Setup|Ide Dekorasi|Desain Ruang Kerja|Rekomendasi Meja}} {{Minimalis|Aesthetic|Modern Scandinavian|Kayu Kokoh}} {{Kamar Sempit|Studio Minimalis|Home Office Cozy}} {{Bikin Betah|Setup Impian|Auto Rapi|Tampil Mewah}}"

2. Buat "seo_desc": Deskripsi persuasif yang PANJANG dan sangat kaya SEO (minimal 3 paragraf). Jejali dengan kata kunci utama, kata kunci LSI, serta pertanyaan retoris pembuka yang menarik minat klik. 
DILARANG KERAS menggunakan kata "shopee" atau "racun shopee" di dalam teks deskripsi maupun hashtag.
- Paragraf 1: Pengenalan produk, masalah yang diselesaikan, dan keyword LSI (misal: dekorasi kamar, inspirasi ruangan, dll).
- Paragraf 2: Keunggulan detail produk (desain, material, daya tahan) dengan keyword relevan.
- Paragraf 3: Call to Action (CTA) ajakan wajib untuk klik link di bawah (Contoh: "Klik link produk di bawah ini untuk melihat detail produk atau membelinya langsung! 👇✨").
- Di bagian paling bawah deskripsi, tambahkan tepat 5-8 hashtag populer dan tertarget di Pinterest (misal: #InspirasiDekorasi #DesainInterior #SetupWorkspace #AestheticHome #MinimalistDesign #IdeKamar).
Seluruh bagian kalimat di deskripsi harus menggunakan Spintax yang bervariasi tinggi agar hasil spin selalu unik!

3. Buat "master_prompt": SATU prompt bahasa Inggris utuh untuk AI Image Generator (Midjourney/ImageFX) yang mendeskripsikan subjek, detail, background, dan pencahayaan, ditulis menggunakan Spintax pada elemen visual utamanya (DILARANG keras menggunakan flag/parameter seperti --ar 9:16 atau 9:16). Contoh: "{{minimalist wooden desk|modern industrial desk}} with {{black metal frame|solid steel legs}} in a {{cozy apartment|sunlit home office}}...".

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
 
WAJIB DAN MUTLAK: Seluruh teks output (seo_title, seo_desc, master_prompt) HARUS ditulis menggunakan format tradisional Spintax {{opsi1|opsi2|opsi3}} pada kata atau frasa kunci di dalamnya agar hasilnya selalu bervariasi setiap kali di-spin. Dilarang keras menghasilkan teks polos tanpa Spintax!
 
Tugas spesifik:
1. Buat "seo_title": Judul Pinterest SEO-LSI Clickbait yang PANJANG (antara 70 hingga 100 karakter). Harus sangat kaya akan kata kunci pencarian utama Pinterest yang relevan dengan topik, digabung dengan hook emosional/clickbait.
DILARANG KERAS DAN DIHARAMKAN menggunakan kata "shopee", "racun", atau nama brand e-commerce lainnya di dalam judul. Orang di Pinterest mencari inspirasi desain, ide, dan estetika, bukan brand marketplace.
Fokus pada kata kunci LSI pencarian Pinterest seperti: ide dekorasi, inspirasi setup, desain interior, gaya minimalis, estetik, modern scandinavian, dll.
Wajib menggunakan format Spintax yang padat.
Contoh format ideal: "{{Inspirasi Setup|Ide Dekorasi|Desain Ruang Kerja|Rekomendasi Meja}} {{Minimalis|Aesthetic|Modern Scandinavian|Kayu Kokoh}} {{Kamar Sempit|Studio Minimalis|Home Office Cozy}} {{Bikin Betah|Setup Impian|Auto Rapi|Tampil Mewah}}"
 
2. Buat "seo_desc": Deskripsi persuasif yang PANJANG dan sangat kaya SEO (minimal 3 paragraf). Jejali dengan kata kunci utama, kata kunci LSI, serta pertanyaan retoris pembuka yang menarik minat klik. 
DILARANG KERAS menggunakan kata "shopee" atau "racun shopee" di dalam teks deskripsi maupun hashtag.
- Paragraf 1: Pengenalan produk, masalah yang diselesaikan, dan keyword LSI (misal: dekorasi kamar, inspirasi ruangan, dll).
- Paragraf 2: Keunggulan detail produk (desain, material, daya tahan) dengan keyword relevan.
- Paragraf 3: Call to Action (CTA) ajakan wajib untuk klik link di bawah (Contoh: "Klik link produk di bawah ini untuk melihat detail produk atau membelinya langsung! 👇✨").
- Di bagian paling bawah deskripsi, tambahkan tepat 5-8 hashtag populer dan tertarget di Pinterest (misal: #InspirasiDekorasi #DesainInterior #SetupWorkspace #AestheticHome #MinimalistDesign #IdeKamar).
Seluruh bagian kalimat di deskripsi harus menggunakan Spintax yang bervariasi tinggi agar hasil spin selalu unik!
 
3. Buat "master_prompt": SATU prompt bahasa Inggris utuh untuk AI Image Generator (Midjourney/ImageFX) yang mendeskripsikan subjek, detail, background, dan pencahayaan, ditulis menggunakan Spintax pada elemen visual utamanya (DILARANG keras menggunakan flag/parameter seperti --ar 9:16 atau 9:16). Contoh: "{{minimalist wooden desk|modern industrial desk}} with {{black metal frame|solid steel legs}} in a {{cozy apartment|sunlit home office}}...".
 
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
            success = False
            res = None
            for model in ["gemini-3.6-flash", "gemini-3.5-flash"]:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
                
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
                        success = True
                        break
                except Exception as e:
                    logger.warning(f"Gemini API Key index {self.current_index} failed with model {model}: {e}. Trying next key...")
            
            if success:
                return res
                
            if not self.switch_key():
                raise ValueError("Semua Gemini API Key gagal.")
            if self.current_index == start_index:
                raise ValueError("Semua Gemini API Key gagal.")

    def brainstorm_ideas(self, theme: str, count: int) -> list[str]:
        self.load_keys()
        if not self.keys:
            raise ValueError("Tidak ada Gemini API Key yang disetting.")

        prompt_instruction = f"""
Berdasarkan tema/topik ini: "{theme}".
Tugasmu adalah memikirkan dan membuat {count} ide judul produk atau sudut pandang promosi produk yang spesifik, unik, estetik, dan memiliki daya tarik tinggi untuk dicari di Pinterest.
Setiap judul harus bervariasi jenis produknya, contoh jika temanya "meja belajar":
- Ide 1 bisa tentang meja belajar minimalis kayu jati
- Ide 2 bisa tentang meja belajar lipat hemat tempat untuk kamar kos
- Ide 3 bisa tentang meja komputer sudut L-shape
- Ide 4 bisa tentang meja belajar aesthetic warna pastel dengan laci penyimpanan
- Ide 5 dst.

Format output HARUS berupa JSON array of strings seperti contoh berikut:
[
  "Judul Ide 1",
  "Judul Ide 2",
  "Judul Ide 3"
]

HANYA kembalikan JSON array tersebut. Jangan tambahkan penjelasan lain.
"""
        start_index = self.current_index
        while True:
            key = self.get_current_key()
            success = False
            res = []
            for model in ["gemini-3.6-flash", "gemini-3.5-flash"]:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
                payload = json.dumps({"contents": [{"parts": [{"text": prompt_instruction}]}]}).encode("utf-8")
                req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
                
                try:
                    with urllib.request.urlopen(req, timeout=20) as resp:
                        data = json.loads(resp.read().decode("utf-8"))
                        text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                        
                        if text.startswith("```json"): text = text[7:]
                        if text.endswith("```"): text = text[:-3]
                        
                        res = json.loads(text.strip())
                        if isinstance(res, list):
                            success = True
                            break
                except Exception as e:
                    logger.warning(f"Gemini Brainstorm Key index {self.current_index} failed with model {model}: {e}. Trying next key...")
            
            if success:
                return res[:count]
                
            if not self.switch_key():
                raise ValueError("Semua Gemini API Key gagal.")
            if self.current_index == start_index:
                raise ValueError("Semua Gemini API Key gagal.")

    def generate_seo_and_prompt(self, basic_title: str, reference_images: list[str]) -> dict:
        return self.generate_prompt_from_image(reference_images, basic_title)

manager = GeminiManager()
