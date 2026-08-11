# Aturan Sistem: Affilia-PinShop Workflow

Setiap kali melakukan perubahan pada modul "Studio" atau "Engine Loop", patuhi alur wajib berikut:
1. **Input UI:** UI harus mendukung input teks (judul, link shopee) dan MULTIPLE images (foto referensi). Tidak boleh memecah prompt UI menjadi beberapa bagian; cukup tampilkan 1 Master Prompt.
2. **Gemini AI:** Selalu gunakan model Vision (misal `gemini-3.6-flash`) untuk menganalisis SEMUA foto referensi beserta judul untuk menghasilkan 1 Master Prompt utuh, 1 SEO Title Pinterest, dan 1 SEO Description Pinterest.
3. **Google Flow:** Sistem Engine Loop WAJIB mengirimkan foto referensi (Image-to-Image/Video) DAN Master Prompt ke jembatan Google Flow (Extension Bridge).
4. **Pinterest Upload:** Selalu sertakan Link Affiliate asal (dari Shopee) saat mengunggah hasil karya akhir (dari Flow) ke Pinterest, bersamaan dengan SEO Title dan Description.
