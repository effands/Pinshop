# Aturan Sistem: Perlindungan Kredensial & Data Lokal Pengguna

Wajib dipatuhi oleh seluruh Agen AI dalam setiap sesi Pair Programming atau perbaikan sistem:

1. **JANGAN PERNAH Mengubah/Menimpa File Data Sensitif**:
   * File `data/settings.json` (berisi API Keys, SpintaxLinks, dll.) dan `storage/accounts.json` (berisi data akun dan cookies browser) merupakan data lokal sensitif milik pengguna.
   * Dilarang keras melakukan perintah git berbahaya seperti `git checkout data/settings.json`, `git reset`, atau menulis file kosong/default ke file tersebut selama update sistem.
   
2. **Proteksi Penggabungan (Merge-on-Save)**:
   * Saat memodifikasi fitur penyimpanan pengaturan (di backend/frontend), selalu prioritaskan pelestarian data dinamis yang sudah ada (seperti `queue` atau `cookies`).
   * Jangan pernah menuliskan data baru ke file konfigurasi tanpa membaca dan menyatukan (*merge*) data lama yang sudah ada di disk terlebih dahulu.

3. **Cara Reset File yang Aman**:
   * Jika ingin memulihkan template konfigurasi default untuk debugging, salin konten default ke file baru (misal `settings.json.example`) daripada langsung menimpa file aktif `settings.json` milik pengguna.
