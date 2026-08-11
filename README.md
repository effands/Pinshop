# 📌 Pinshop — Autopilot Pinterest Affiliate Automation Suite

Pinshop adalah aplikasi otomasi cerdas kelas premium (SaaS-styled dashboard) yang dirancang untuk mempercepat penjualan produk affiliate (seperti Shopee, TikTok, dll) di Pinterest secara autopilot. 

Aplikasi ini menggabungkan kecanggihan **Gemini AI** (untuk meracik judul clickbait, deskripsi SEO persuasif, dan master prompt), **Google Flow (ImageFX & Video)** (untuk merender media HD beresolusi tinggi), dan **Pinterest Business Browser Session** (untuk memposting secara terjadwal dan otomatis).

---

## ✨ Fitur Utama

1. **📋 Antrean Posting Massal (Bulk Queue System)**
   - Masukkan puluhan hingga ratusan produk sekaligus ke dalam antrean postingan massal.
   - Setiap item menyimpan judul produk, link affiliate, dan gambar referensi secara mandiri.
   - **Dua Alur Kerja Fleksibel**:
     - *Mode Cepat*: Cukup masukkan data dasar dan klik *Queue*, AI Gemini akan otomatis memproses SEO & Prompt di latar belakang.
     - *Mode Kustom*: Klik *Generate SEO* terlebih dahulu, edit judul/deskripsi hasil racikan AI sesuka Anda, lalu masukkan teks hasil kustomisasi tersebut ke dalam antrean.

2. **⚙️ Kontrol Penuh Google Flow (Gambar & Video)**
   - **Aspek Rasio Fleksibel (Foto)**: Pilih antara `9:16` (Pinterest/Reel), `1:1` (Square), `16:9` (Landscape), `4:3`, atau `3:4`.
   - **Aspek Rasio & Durasi (Video)**: Mendukung rasio video `9:16` atau `16:9` dengan durasi kustom `4s`, `6s`, `8s`, atau `10s`.
   - **Auto-Batching**: Memisahkan request rendering berjumlah besar menjadi batch-batch kecil berukuran 4 untuk menghindari limitasi API Google Flow.

3. **🧠 Racikan Spintax Gemini AI & Anti-Duplikasi**
   - Secara bawaan memaksa Gemini AI untuk menghasilkan teks dalam format Spintax tradisional `{opsi1|opsi2|opsi3}`.
   - Sistem spintax diparsing secara acak di setiap iterasi posting sehingga judul dan deskripsi Pinterest selalu unik untuk menghindari deteksi spam.
   - Pembersihan otomatis parameter aspect ratio bawaan Midjourney (seperti `--ar 9:16` atau `9:16`) dari prompt sebelum dikirim ke Google Flow.

4. **🎨 Galeri Media Terintegrasi (Gallery & CRUD)**
   - Monitor seluruh gambar dan video hasil render yang berhasil didownload di dalam tab Gallery terpusat.
   - Mendukung CRUD dasar (menampilkan grid media, link download langsung, dan hapus permanen dengan icon tong sampah).

5. **🛡️ Jadwal Operasional Pintar & Anti-Ban**
   - **Jeda Waktu Dinamis (Detik)**: Batasi frekuensi posting dengan jeda waktu kustom dalam satuan detik.
   - **Jam Kerja Otomatis**: Batasi rentang jam mulai dan berhenti operasional autopilot.
   - **Tanda Tangan AI**: Otomatis memberikan label "AI-Modified/AI-Generated Person" pada Pinterest Business.

---

## 📂 Struktur Proyek

```text
Pinshop/
├── backend/            # FastAPI Python server (Pipeline, Gemini & Pinterest posting)
│   ├── main.py         # REST & WebSocket API endpoints
│   ├── engine_loop.py  # Orchestration Autopilot & Queue loop
│   ├── gemini_manager.py # Gemini AI request handlers
│   └── spintax.py      # Spintax parsing utilities
├── engine/             # Google Flow Extension Bridge (OmniFlash)
├── frontend/           # React + Vite Client Dashboard
│   ├── src/
│   │   ├── App.jsx     # Dashboard UI premium & State management
│   │   └── index.css   # Glassmorphic dark styling & animations
├── data/               # Persistent configuration storage
└── storage/            # Generated media & gallery directory
```

---

## 🚀 Panduan Instalasi & Penggunaan

### 📋 Prasyarat
1. **Python 3.10+** terinstal di sistem Windows Anda.
2. **Node.js 18+** terinstal untuk menjalankan dashboard React.
3. Ekstensi browser Google Flow terpasang aktif di profil Google Chrome Anda.

### 🏃 Menjalankan Aplikasi
Cukup klik dua kali file batch di root folder:
```bash
start.bat
```
Script ini akan mendeteksi dependensi, memasang paket python/node secara otomatis, lalu membuka browser ke alamat Dashboard Premium Pinshop:
👉 **`http://localhost:5173`** (atau port alternatif Anda)

---

## 🛠️ Konfigurasi Tambahan
* **Pilih Akun**: Tambahkan cookie akun Pinterest Anda di tab **Settings**. Pastikan statusnya berlabel hijau `Valid` sebelum memulai autopilot.
* **Gemini API Keys**: Masukkan satu atau beberapa API Key Gemini (satu per baris). Gunakan tombol **Test & Sort Keys** untuk menyortir dan membersihkan kunci API yang tidak valid secara otomatis.

---

*Dibuat dengan ❤️ untuk efisiensi maksimal dalam optimasi affiliate marketing.*
