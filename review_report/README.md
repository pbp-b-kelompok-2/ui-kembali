# Modul 5 — Review & Report

**Proyek:** UIKembali

**Penanggung jawab:** Muhammad Rifky Padjri — 2506585800

**Model utama:** `Review`, `Report`, `ReportSubmission`

**Relasi modul:** `katalog.ItemRequest`, `katalog.Item`, dan `settings.AUTH_USER_MODEL`

**Antarmuka:** Django Template, Tailwind CSS, dan HTMX

Modul ini memungkinkan pengadopsi atau pembeli memberikan ulasan setelah transaksi
selesai, serta melaporkan barang atau pengguna yang bermasalah. Ulasan menjadi
informasi reputasi publik, sedangkan laporan ditangani secara privat oleh petugas
berizin.

## Fitur

- CRUD ulasan dengan rating bilangan bulat 1–5 dan teks 10–1.000 karakter.
- Satu ulasan per transaksi, dijaga dengan relasi OneToOne dan constraint database.
- Halaman **Ulasan Saya**, detail ulasan, dan daftar ulasan yang diterima pemilik.
- Rata-rata rating dan jumlah ulasan dihitung dari data aktual, termasuk setelah
  ulasan diedit atau dihapus. Kondisi kosong menampilkan **Belum ada ulasan**.
- Filter ulasan berdasarkan rating dan jenis transaksi adopsi/pembelian, serta
  pagination 10 data per halaman.
- Pelaporan barang atau pengguna tanpa harus menyelesaikan transaksi terlebih dahulu.
  Satu laporan harus memiliki tepat satu target, kategori, dan deskripsi 20–2.000 karakter.
- Halaman **Laporan Saya** dengan filter status, pagination, detail privat, serta
  edit/hapus selama laporan masih **PENDING**.
- Moderasi melalui Django admin dengan alur
  **PENDING → IN_REVIEW → RESOLVED / REJECTED**.
- Pencatatan petugas, waktu pemeriksaan/penutupan, catatan internal, dan hasil
  penanganan yang dapat dibaca pelapor.
- Form, edit/hapus, filter, dan pagination menggunakan HTMX, dilengkapi validasi,
  toast bersama, indikator menyimpan, serta fallback form/navigasi HTML biasa.
- Layout responsif menggunakan Tailwind CSS 4.1.13 tanpa preflight, mewarisi
  `base.html` melalui `base_review_report.html`.

## Keamanan dan aturan akses

- Hanya requester aktif pada `ItemRequest` berstatus **SELESAI** yang dapat
  memberikan ulasan kepada pemilik barang. Status barang selesai saja tidak cukup.
- Penulis dan penerima ulasan ditentukan dari transaksi di server; pengguna tidak
  dapat menentukan identitas tersebut melalui formulir.
- Review diri sendiri dilarang. Hanya penulis boleh mengubah atau menghapus ulasannya.
- Laporan hanya dapat dibaca pelapor atau staff aktif dengan izin khusus
  `review_report.moderate_report`. Pihak terlapor tidak otomatis mendapatkan akses.
- Pelapor, status awal, dan identitas petugas ditentukan server. Pelaporan diri
  sendiri maupun barang sendiri dilarang.
- Pelapor tidak dapat mengedit atau menghapus laporan setelah pemeriksaan dimulai.
  Catatan internal tidak ditampilkan pada halaman pelapor.
- Duplikasi laporan aktif dari pelapor ke target yang sama dicegah oleh constraint.
  Maksimal lima pengiriman berhasil per akun dalam satu jam; `ReportSubmission`
  mempertahankan hitungan meskipun laporan PENDING dihapus.
- Tidak ada pemblokiran barang atau akun otomatis berdasarkan jumlah laporan.
- Aksi perubahan memakai POST dan proteksi CSRF. Teks pengguna di-escape oleh Django.
  Sesi kedaluwarsa pada HTMX diarahkan melalui navigasi penuh ke login.
- Soft-delete barang tetap mempertahankan riwayat. Relasi PROTECT mencegah
  penghapusan permanen yang merusak data review/laporan terkait.

## Integrasi dengan modul lain

| Bagian | Integrasi |
| --- | --- |
| Katalog dan transaksi — Owen | Memakai ItemRequest sebagai bukti transaksi selesai; tombol Beri Ulasan atau Lihat/Edit Ulasan tersedia dari transaksi terkait. |
| Detail barang — Owen | Tombol Laporkan Barang/Pengguna dan ringkasan rating pemilik. |
| Autentikasi/profil — Elvis | Memakai akun dan sesi login bersama, menampilkan reputasi, serta akses dari profil dan riwayat transaksi. |
| Navigasi bersama | Menu Ulasan & Laporan membuka halaman utama modul; navigasi sekundernya berisi Ulasan Saya dan Laporan Saya. |
| Django admin | Pemeriksaan laporan oleh petugas berizin, termasuk transisi status dan hasil penanganan. |

Modul ini tidak memanggil Public API eksternal tambahan. Filter memakai data
transaksi, ulasan, dan laporan dari database. Integrasi API eksternal aplikasi
ditangani modul terkait, seperti UI SSO dan OpenStreetMap.

## Halaman utama

| URL | Fungsi |
| --- | --- |
| `/review-report/` | Pintu masuk Ulasan & Laporan |
| `/review-report/transaksi/` | Riwayat transaksi pengguna |
| `/review-report/transaksi/<uuid>/` | Form ulasan transaksi selesai |
| `/review-report/ulasan/saya/` | Ulasan yang ditulis sendiri |
| `/review-report/pengguna/<int>/ulasan/` | Ulasan yang diterima pemilik |
| `/review-report/laporan/saya/` | Daftar laporan privat sendiri |
| `/admin/review_report/report/` | Moderasi laporan |

## REST API (untuk aplikasi mobile Flutter)

Modul ini menyediakan web service Django REST Framework di bawah
`/api/v1/review-report/`. Kodenya ada di `serializers.py`, `api_views.py`, dan
`api_urls.py`. View API memakai ulang `services.py`, sehingga aturan bisnis
website dan aplikasi mobile identik.

**Autentikasi:** `SessionAuthentication` (cookie sesi login, sama seperti API
katalog). Permintaan tulis (POST/PUT/PATCH/DELETE) memerlukan header CSRF.
**Pagination:** `?page=N`, 10 data per halaman. Bentuk respons daftar:
`{"count", "page", "num_pages", "results": [...]}`.

| Method | Endpoint | Akses | Fungsi |
| --- | --- | --- | --- |
| GET | `meta/` | Publik | Pilihan kategori/status laporan, jenis transaksi, rating untuk dropdown |
| GET | `transactions/` | Login | Riwayat transaksi dengan `review_id` dan `can_review` |
| POST | `transactions/<uuid>/review/` | Requester transaksi SELESAI | Membuat ulasan (`rating`, `comment`) |
| GET | `reviews/mine/` | Login | Ulasan Saya; filter `?rating=1..5`, `?transaction_type=ADOPSI\|JUAL` |
| GET | `reviews/<uuid>/` | Publik | Detail ulasan |
| PUT/PATCH | `reviews/<uuid>/` | Penulis | Mengubah ulasan (PATCH boleh sebagian) |
| DELETE | `reviews/<uuid>/` | Penulis | Menghapus ulasan |
| GET | `users/<int>/reviews/` | Publik | Ulasan yang diterima penjual, plus `summary` (`average`, `count`) |
| GET | `reports/` | Login | Laporan Saya; filter `?status=`, `?category=` |
| POST | `reports/` | Login | Membuat laporan: `category`, `description`, dan tepat satu dari `target_item` (UUID) / `target_user` (id) |
| GET | `reports/<uuid>/` | Pelapor atau moderator | Detail laporan privat (tanpa `internal_notes`) |
| PUT/PATCH | `reports/<uuid>/` | Pelapor, status PENDING | Mengubah `category` / `description` |
| DELETE | `reports/<uuid>/` | Pelapor, status PENDING | Menghapus laporan |

**Batas input:** `rating` 1–5, `comment` 10–1.000 karakter, `description` laporan
20–2.000 karakter, `category` salah satu dari `SCAM`, `PROHIBITED`, `MISLEADING`,
`HARASSMENT`, `SPAM`, `OTHER`.

**Kode respons:**

| Kode | Arti |
| --- | --- |
| 200 / 201 / 204 | Berhasil / dibuat / dihapus |
| 400 | Input tidak valid (rincian per field di body) |
| 403 | Belum login atau bukan hak pengguna (mis. mengulas transaksi orang lain, melaporkan diri sendiri) |
| 404 | Data tidak ada, atau laporan milik orang lain (keberadaannya tidak dibocorkan) |
| 409 | Aturan bisnis tidak terpenuhi: transaksi belum selesai, ulasan ganda, laporan sudah diperiksa, laporan aktif ganda, atau batas 5 laporan/jam |

Contoh membuat ulasan:

```http
POST /api/v1/review-report/transactions/<uuid>/review/
Content-Type: application/json

{"rating": 5, "comment": "Barang sesuai deskripsi, penjual ramah."}
```

Moderasi laporan tetap dilakukan melalui Django admin; moderator berizin hanya
dapat membaca laporan lewat API. Test API: `python manage.py test review_report.tests.test_api`.

## Pengujian

Pengembangan memakai TDD (Red → Green → Refactor). Pengujian mencakup validasi
model/form, constraint database, kelayakan transaksi, CRUD, hak akses, privasi,
moderasi, agregat rating, filter, pagination, CSRF, soft-delete, dan respons HTMX.
Functional test Selenium memeriksa alur browser dan tampilan responsif.

Jalankan dari root repository setelah memasang dependensi pengembangan:

```powershell
python -m pip install -r requirements-dev.txt
python manage.py test review_report --exclude-tag=browser

python -m coverage run --source=review_report --omit="*/tests/*,*/migrations/*" manage.py test review_report --exclude-tag=browser
python -m coverage report

$env:RUN_BROWSER_TESTS = "1"
python manage.py test review_report.tests.test_browser
Remove-Item Env:RUN_BROWSER_TESTS
```

Test unit/integrasi tidak menghubungi SSO atau Nominatim sungguhan. Test browser
memerlukan Chrome serta akses ke CDN yang dipakai antarmuka. Catatan hasil
pengujian, bukti TDD, batas verifikasi, dan langkah demo tersedia di
[dokumentasi teknis](../docs/REVIEW_REPORT.md).

## AI Disclosure

- **Tool:** Codex (OpenAI).
- **Penggunaan:** membantu perencanaan, implementasi model/form/services/view/template,
  penulisan test, refactor, debugging, pemeriksaan browser, dan dokumentasi modul.
- **Perbaikan selama pengembangan:** penanganan error validasi model pada form,
  resolusi target laporan, URL tujuan setelah swap HTMX, indikator menyimpan,
  serta navigasi dan layout responsif.
- **Batas verifikasi:** pengujian lokal menggunakan SQLite; locking konkuren pada
  PostgreSQL dan autentikasi SSO sungguhan belum dibuktikan oleh test lokal tersebut.
  Test browser mencakup skenario yang ditulis, bukan seluruh kombinasi perangkat.

Lihat juga [README proyek](../README.md) untuk deskripsi aplikasi, anggota kelompok,
serta informasi modul lainnya.
