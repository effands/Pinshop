# PANDUAN PENGEMBANGAN SISTEM (UNTUK AGEN AI)
Aturan Mutlak & Arsitektur Failsafe untuk Menghindari Bug State, Port, Loop, dan Script Startup.

---

## 1. MANAJEMEN STATE & PERSISTENSI DATA (JSON/DB)
Setiap kali melakukan operasi baca/tulis ke file konfigurasi atau database flat-file (seperti settings.json, cookies, atau data akun):

* **Prinsip Merge-by-Default (Anti-Overwrite)**: 
  Jangan pernah menulis payload baru dari frontend langsung ke file disk secara utuh (misal: json.dump(payload)). Selalu baca file yang sudah ada di disk terlebih dahulu, lakukan penggabungan (merge) tingkat objek/array untuk field yang tidak dikirim oleh UI (seperti token, queue, cookies, atau history), baru simpan kembali ke disk.
* **Status Isolation**: 
  Pisahkan data konfigurasi statis (seperti waktu jeda, tipe media) dengan data dinamis/antrean (seperti antrean produk, status akun). Jika memungkinkan, simpan di file terpisah (misal settings.json vs queue.json) untuk meminimalkan risiko kontaminasi state akibat kegagalan penulisan.
* **Auto-Recovery on Corrupted JSON**: 
  Jika file JSON rusak atau gagal di-parse saat dibaca, buat mekanisme backup otomatis (misal: .bak) sebelum menulis ulang file baru dengan template default. Jangan biarkan aplikasi crash hanya karena kegagalan parser JSON.
* **Cara Reset File yang Aman**:
  Jika ingin memulihkan template konfigurasi default untuk debugging, salin konten default ke file baru (misal `settings.json.example`) daripada langsung menimpa file aktif `settings.json` milik pengguna.
* **Kewajiban Pengujian Kode Mandiri (Failsafe Testing)**:
  Setiap kali Agen AI selesai melakukan modifikasi kode (terutama python/javascript/batch script), agen WAJIB melakukan pengujian sintaksis secara mandiri sebelum menyatakan pekerjaan selesai. Untuk Python, selalu lakukan verifikasi dengan menjalankan modul/file yang diubah (misal `python -m backend.main`) untuk menjamin tidak ada SyntaxError atau ImportError. Dilarang keras menyerahkan hasil kode yang belum divalidasi ke pengguna untuk meminimalkan trial-error yang tidak efisien.

---

## 2. ATURAN STATE MACHINE ANTRIAN & ENGINE LOOP
Untuk mesin pemroses antrean latar belakang (background queue engine):

* **Siklus Hidup Status yang Jelas**: 
  Setiap item antrean wajib mengikuti siklus status: PENDING ➔ RUNNING ➔ (SUCCESS / FAILED).
* **Failsafe Transition (Anti-Stuck)**: 
  Status RUNNING adalah status transisi sementara. DILARANG KERAS membiarkan item tetap dalam status RUNNING jika proses keluar lebih awal (early exit/continue) atau terjadi exception/error di tengah jalan.
* **Try-Finally Pattern untuk State Recovery**:
  Gunakan blok try...except...finally atau helper penangan status untuk memastikan status antrean aktif dikembalikan ke PENDING (jika ingin di-retry) atau diubah ke FAILED sebelum program melanjutkan ke iterasi berikutnya atau melompat keluar loop (continue).
* **Self-Healing on Startup**:
  Setiap kali aplikasi web/server backend baru dinyalakan (lifespan startup event), wajib jalankan fungsi pembersihan untuk memindai file konfigurasi antrean. Ubah semua item yang tersangkut di status RUNNING kembali menjadi PENDING atau FAILED secara otomatis.

---

## 3. AUDIT PORT BENTROK & MULTI-KOMUNIKASI (EXTENSION/API)
Jika aplikasi berjalan di lingkungan lokal PC pengguna dan berkomunikasi dengan ekstensi Chrome atau API eksternal:

* **Audit Hardcoded Strings Terlebih Dahulu**:
  Sebelum mengubah port API backend, lakukan pencarian regex global (grep) untuk mendeteksi semua string port, IP address, websocket rute, atau callback URL di seluruh project (termasuk folder extension vendor, manifest, file .env, file javascript frontend, dan python backend).
* **Pemetaan Port Jembatan yang Unik**:
  Jika pengguna memiliki aplikasi lain yang sejenis (misal menggunakan modul otomasi browser/Google Flow yang sama), bedakan tidak hanya port backend API utama, tetapi juga port komunikasi internal jembatan:
  - Port WebSocket Bridge (WS_PORT)
  - Port HTTP Callback (HTTP_PORT)
* **Dynamic Extension Configuration**:
  Rancang ekstensi Chrome agar menerima konfigurasi URL WebSocket dan HTTP callback secara dinamis dari backend API saat jabat tangan (handshake) pertama kali, daripada menulis mati (hardcode) port tersebut di file background.js ekstensi.
* **Release Port Sebelum Bind**:
  Di script startup, selalu jalankan deteksi proses lama yang menduduki port target menggunakan perintah utilitas sistem (seperti netstat atau lsof), lalu matikan PID tersebut secara otomatis sebelum mencoba melakukan binding port baru (uvicorn run).

---

## 4. PENANGANAN RATE LIMIT & ROTASI KUNCI API
Jika aplikasi mengintegrasikan API pihak ketiga dengan batas kuota gratis yang ketat:

* **Warning vs Error Logging**:
  Jika salah satu API key dari daftar kunci yang disediakan terkena batas kuota (rate limit/quota exceeded), log kejadian tersebut sebagai WARNING atau INFO (bukan ERROR) jika sistem berhasil melakukan rotasi dan melanjutkan proses menggunakan kunci cadangan berikutnya. Jangan menakuti pengguna dengan pesan log error merah yang mengesankan aplikasi crash.
* **Circular Key Rotation**:
  Logika rotasi kunci wajib memproses seluruh daftar kunci yang tersedia secara melingkar (circular). Jangan menaikkan pengecualian (exception) kecuali jika seluruh kunci dalam daftar sudah dicoba dan semuanya mengembalikan kegagalan.

---

## 5. OTOMASI BROWSER & MANAJEMEN PROSES LOCKED (PENTING)
Jika aplikasi menggunakan Selenium, Playwright, Puppeteer, atau browser khusus:

* **Pembersihan Singleton Lock (Anti-Profile Locked)**:
  Saat meluncurkan browser dengan profil pengguna (User Data), buat penghapus otomatis untuk file lock seperti `SingletonLock` atau file sejenis di direktori profil sebelum meluncurkan browser. Browser yang crash sebelumnya sering meninggalkan file ini dan memblokir peluncuran berikutnya.
* **Orphaned Process Killer**:
  Saat aplikasi web baru dimulai, lakukan pemindaian dan matikan semua proses browser latar belakang yang tidak sah (seperti chrome.exe, chromedriver.exe, playwright, dsb.) yang tersisa dari sesi crash sebelumnya agar tidak memakan RAM atau mengunci profil browser.

---

## 6. PENANGANAN ENCODING CONSOLE WINDOWS (CHARMAP ERROR)
Khusus untuk aplikasi berbasis Python/Node.js yang berjalan di Windows CMD:

* **Anti-Unicode Crash (Charmap Error)**:
  Windows CMD secara bawaan menggunakan encoding CP1252/Charmap. Mencetak emoji (✅, ❌) atau karakter Asia ke konsol tanpa proteksi akan langsung menghentikan paksa server dengan `UnicodeEncodeError`. 
  Selalu paksa stdout/stderr menggunakan UTF-8 di bagian paling atas file entri utama (`main.py`):
  ```python
  import sys
  if hasattr(sys.stdout, "reconfigure"):
      sys.stdout.reconfigure(encoding="utf-8")
  if hasattr(sys.stderr, "reconfigure"):
      sys.stderr.reconfigure(encoding="utf-8")
  ```

---

## 7. STRUKTUR LOKASI FILE & KEBERSIHAN GIT
* **Relative Pathing (Anti-C:\ Hardcode)**:
  Dilarang menggunakan path absolut (seperti `C:\Users\...\storage`). Selalu gunakan path relatif terhadap root workspace aplikasi (misal menggunakan modul `pathlib.Path(__file__).parent`).
* **GitIgnore Strict Policy**:
  Jangan pernah melakukan commit file sementara, screenshots, generated media (foto/video hasil render), logs, database lokal (sqlite/accounts.json), dan token sesi ke Git. Wajib masukkan folder penyimpanan lokal tersebut ke file `.gitignore`.

---

## 8. FORMAT & STABILITAS SCRIPT BATCH WINDOWS (.bat)
Untuk script otomatisasi startup di Windows Command Prompt (cmd.exe):

* **Mutlak Gunakan CRLF (Windows Line Ending)**:
  Format ujung baris file script batch wajib menggunakan CRLF. Jika file diubah oleh runner AI menjadi format LF, interpretasi perintah batch akan rusak dan jendela CMD akan langsung menutup seketika tanpa pesan error.
* **Hindari Parentheses Mismatch di Blok if/for**:
  Jangan menulis tanda kurung di dalam baris perintah echo yang terbungkus oleh blok tanda kurung (...) bawaan pernyataan if atau for. Gunakan escape caret (^) atau hilangkan tanda kurung tersebut di teks echo.
* **Non-Interactive Sleep (Anti-Timeout Error)**:
  Jangan pernah menggunakan perintah timeout /t di dalam script batch yang dijalankan melalui terminal non-interaktif agen AI, karena akan memicu kegagalan input redirection. Selalu gunakan alternatif ping lokal:
  ping 127.0.0.1 -n <detik+1> > nul
