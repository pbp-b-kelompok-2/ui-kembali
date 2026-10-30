# Review & Report — Muhammad Rifky Padjri

Modul Django untuk ulasan transaksi dan laporan privat. URL utama:

| URL | Kegunaan |
| --- | --- |
| `/review-report/transaksi/` | Riwayat request milik pengguna sebagai requester/pemilik |
| `/review-report/ulasan/saya/` | Review yang ditulis sendiri, filter rating/jenis transaksi, pagination |
| `/review-report/pengguna/<id>/ulasan/` | Review yang diterima pemilik dan ringkasan rating publik |
| `/review-report/transaksi/<uuid>/` | Beri ulasan untuk satu request selesai |
| `/review-report/laporan/saya/` | Daftar laporan privat dengan filter status dan pagination |
| `/review-report/laporkan/barang/<uuid>/` | Laporkan barang tanpa syarat transaksi |
| `/review-report/laporkan/pengguna/<id>/` | Laporkan pengguna tanpa syarat transaksi |
| `/admin/review_report/report/` | Pemeriksaan laporan oleh staff berizin |

Detail, edit, dan hapus tersedia dari halaman daftar/detail. Hapus hanya melalui POST.

## Aturan dan arsitektur

- `forms.py` memvalidasi input; `services.py` memeriksa aturan bisnis dan menyimpan perubahan; `views.py` memproses HTTP; model menyediakan constraint database.
- Review 1–5, komentar 10–1000 karakter, satu review per ItemRequest. Hanya requester request `SELESAI` yang dapat menilai pemilik. Status Item `SELESAI` saja tidak cukup. Identitas bukan field form pengguna. Hanya penulis dapat mengubah/menghapus. Penghapusan nyata memungkinkan review dibuat kembali pada transaksi yang sama.
- Agregat dihitung dari review yang tersimpan, bukan counter manual. Filter daftar tidak mengubah ringkasan keseluruhan reputasi pemilik.
- Laporan harus memiliki tepat satu target, deskripsi 20–2000 karakter. Tidak boleh melaporkan diri atau barang sendiri. Laporan aktif duplikat dari pelapor untuk target yang sama ditolak oleh constraint; kasus baru setelah laporan ditutup diperbolehkan. Pembuatan dibatasi 5 laporan tersimpan dalam satu jam. Ini perlindungan dasar, bukan sistem antispam terdistribusi.
- Hanya pelapor boleh edit/hapus selama `PENDING`; sesudahnya terkunci. Isi hanya dapat dibaca pelapor dan petugas berizin. Target laporan tidak otomatis mendapat akses. Tidak ada pemblokiran otomatis berdasarkan jumlah laporan.
- Moderator harus aktif, staff, dan memiliki permission `review_report.moderate_report`. Alur: `PENDING -> IN_REVIEW -> RESOLVED / REJECTED`. Penutupan wajib memiliki hasil publik. Catatan internal hanya ada di admin; hasil publik tersedia untuk pelapor. `reviewed_by` mencatat pelaku transisi terakhir, `reviewed_at` awal pemeriksaan, `resolved_at` penutupan. Belum ada tabel riwayat semua transisi; Django admin juga memiliki log perubahan bawaannya.
- Relasi review/request dan target/pelapor/petugas laporan menggunakan `PROTECT`. Soft-delete barang tetap mempertahankan riwayat; detail publik barang terhapus tetap ditangani katalog. Akun/barang/request yang dilindungi tidak dapat di-hard-delete tanpa menangani relasinya. Kebijakan retensi/penghapusan akun kelompok perlu memperhitungkan ini.
- Transaksi database dan re-read baris digunakan untuk perubahan. Penguncian baris efektif pada PostgreSQL; SQLite tidak membuktikan perilaku lock PostgreSQL dalam pengujian paralel. Constraint tetap menangani keunikan dan konflik diuji dengan simulasi IntegrityError.
- Review publik; laporan privat. Teks pengguna di-escape Django. CSRF aktif. HTML modul tidak disimpan ke snapshot history HTMX; respons memakai no-store dan Vary. Login HTMX menggunakan HX-Redirect agar halaman SSO tidak ditempel di area konten.

## Tampilan dan integrasi

`page.html -> base_review_report.html -> base.html`. Tailwind browser **4.1.13** mengikuti katalog, theme/utilities tanpa preflight, tanpa runtime kedua. Font Figtree dan kerangka navbar/footer bersama tetap digunakan. Ikon lokal bersumber dari node Figma `20:11438`; foto barang tetap dinamis. Tag opsional dan angka dampak lingkungan contoh tidak diimplementasikan.

Form, edit/hapus, filter, dan pagination memakai HTMX dengan fallback navigasi/form biasa. Error 403/409/422 ditampilkan di konten, toast memakai `static/js/toast.js`, fokus dipindah ke pesan error. Tombol dinonaktifkan dan indikator tampil selama simpan.

Integrasi yang sudah ada:

- Detail katalog: tautan laporan barang/pemilik, reputasi pemilik, dan tombol review hanya untuk requester request selesai; sesudah diulas menuju detail/edit review.
- Profil: tautan Ulasan Saya, Laporan Saya, reputasi, dan riwayat. Navbar Transaksi menuju riwayat berbasis ItemRequest nyata di modul ini.
- Halaman riwayat mempertahankan transaksi barang soft-delete dan tidak membuka transaksi pihak ketiga.
- Template `_transaction_link.html` dapat dipakai dari baris request Owen: `{% include 'review_report/_transaction_link.html' with req=req %}`. Muat relasi `review`, `item`, dan requester pada queryset untuk menghindari query berulang.

Dependensi kelompok yang belum digabung:

- Pada referensi remote yang diperiksa, `complete_request()` ada di `feat/owen-requests` dan juga garis pengembangan `feat/owen-osm`, belum di main. Modul ini memakai kontrak ItemRequest yang sudah ada dan tidak menyalin atau menggabungkan branch Owen. Pusat pengajuan/penyelesaian katalog pada checkout ini masih bergantung pada integrasi Owen; demo memakai transaksi sintetis yang telah selesai.
- `feat/vis` memiliki profil/riwayat yang lebih baru. Integrasi saat ini ditambahkan pada template checkout aktif. Setelah branch Elvis masuk, pertahankan tautan/ringkasan modul dan hubungkan baris riwayat barunya ke `_transaction_link.html`.
- Chat/forum tidak menjadi dependensi aturan review/report. Public API tambahan tidak ditambahkan. Ketentuan filter Public API per anggota masih perlu diklarifikasi dengan asdos; filter database rating, jenis transaksi, dan status sudah tersedia.

## Menjalankan dan demo lokal

PowerShell dari root repository:

```powershell
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe manage.py migrate
.venv/Scripts/python.exe manage.py seed_review_report_demo --password "Ganti-dengan-password-demo"
.venv/Scripts/python.exe manage.py runserver
```

Login di `http://127.0.0.1:8000/admin/login/` memakai password yang diberikan pada command. Lalu buka `/review-report/transaksi/` atau `/katalog/`.

| Akun sintetis | Fungsi |
| --- | --- |
| `rr_demo_buyer` | Review adopsi belum diulas, review pembelian yang dapat diedit, serta laporan pending |
| `rr_demo_seller` | Melihat reputasi, menguji tidak boleh mengedit review pembeli |
| `rr_demo_other` | Menguji isolasi data/privasi dari pihak ketiga |
| `rr_demo_moderator` | Memeriksa dan menutup laporan melalui admin |

Semua akun demo diberi `is_staff` agar dapat login lokal melalui admin tanpa menambahkan endpoint bypass SSO. Hanya moderator memperoleh permission moderasi; akun lain tidak diberi permission model atau superuser. Command menolak mode PRODUCTION, memakai data sintetis dengan ID deterministik, dapat diulang tanpa menggandakan transaksi, dan menolak akun bernama sama yang bukan milik grup demo. Pengulangan memperbarui password demo tetapi tidak mereset status laporan/review yang sudah ada.

Skenario demo:

1. Buyer: buka transaksi adopsi selesai, kirim review, edit, lalu hapus. Periksa perubahan ringkasan reputasi seller.
2. Buyer: request pending dan barang selesai dengan request pending tidak menyediakan Beri Ulasan. Akses URL langsung juga ditolak.
3. Buyer: buat laporan barang/pengguna dari detail katalog, edit sebelum pemeriksaan, dan lihat Laporan Saya.
4. Moderator: buka laporan di admin, ubah PENDING ke IN_REVIEW, isi catatan internal, kemudian RESOLVED/REJECTED dengan hasil publik.
5. Buyer: laporan terkunci dan hasil publik terlihat. Akun seller/other tidak boleh membaca detail laporan tersebut. Uji desktop dan ponsel.

## Pengujian dan TDD

```powershell
# Django unit/integration; test browser di-skip secara eksplisit pada mode ini.
.venv/Scripts/python.exe -m coverage run manage.py test review_report --noinput
.venv/Scripts/python.exe -m coverage report

# Seluruh aplikasi dan browser. Chrome/Selenium Manager membutuhkan akses jaringan.
$env:RUN_BROWSER_TESTS = '1'
.venv/Scripts/python.exe -m coverage run manage.py test --noinput
.venv/Scripts/python.exe -m coverage report
Remove-Item Env:RUN_BROWSER_TESTS

# Browser saja
$env:RUN_BROWSER_TESTS = '1'
.venv/Scripts/python.exe manage.py test review_report.tests.test_browser --noinput
Remove-Item Env:RUN_BROWSER_TESTS

.venv/Scripts/python.exe manage.py makemigrations review_report --check --dry-run
.venv/Scripts/python.exe manage.py check
```

`.coveragerc` mengukur kode aplikasi review_report dengan branch coverage; tests dan migrasi dikecualikan, batas gagal 90%. Selenium menjalankan live server Django, session cookie sintetis dan CSRF nyata, tanpa menghubungi SSO atau Nominatim. Tiga test browser memeriksa CRUD review/report, error server HTMX, filter, lock, toast, keyboard, tombol/indikator simpan, layout 390/768 px, serta ukuran ikon. Screenshot penuh disimpan di `.artifacts/review_report/` yang diabaikan Git. Browser membutuhkan CDN Tailwind/HTMX seperti halaman katalog.

Catatan Red -> Green yang benar-benar diamati:

| Tahap | Red yang dijalankan | Sesudah implementasi |
| --- | --- | --- |
| Model review | Import Review belum tersedia | 3 test hijau |
| Kelayakan review | services belum tersedia | 8 test kumulatif hijau |
| CRUD/agregat review | update_review/rating_summary belum tersedia | 10 test kumulatif hijau |
| Model laporan | Report belum tersedia | 13 test kumulatif hijau |
| CRUD laporan | create_report belum tersedia | 18 test kumulatif hijau |
| Moderasi | admin/moderate_report belum tersedia | 22 test kumulatif hijau |
| HTTP | namespace review_report belum tersedia | 9 test HTTP hijau setelah pekerjaan dilanjutkan |
| Integrasi | 6 test: tautan/riwayat belum ada, URL tujuan HTMX salah, exception form, resolusi target laporan | 37 test kumulatif hijau |
| Privasi history | hx-history=false belum ada | Test regresi hijau |
| Demo command | seed_review_report_demo belum tersedia | 3 test demo hijau |
| Layout ponsel | Chrome menemukan scrollWidth 565 pada viewport 390 | Setelah penyesuaian header terisolasi, test ponsel hijau |
| Indikator simpan | Chrome membuktikan indikator tidak terlihat selama request tertahan | Selector indikator diperbaiki, test hijau |

Pengujian awal proyek sempat gagal import `cas` karena dependensi lingkungan, bukan kegagalan bisnis. Setelah python-cas dipasang, baseline 83 tests lulus. Browser awal juga gagal mengambil driver karena sandbox jaringan dan sempat membaca elemen stale saat swap HTMX; keduanya dibedakan dari kegagalan aplikasi. Commit berisi implementasi dan tests dalam keadaan hijau, bukan commit Red terpisah. Tabel ini adalah catatan eksekusi sesi, bukan klaim bahwa setiap fase Red tersimpan sebagai commit Git.

Catatan pemeriksaan proyek: `makemigrations --check --dry-run` seluruh app menemukan drift bawaan `auth_ssoui.Profile.pfp` (usulan migrasi 0008), sementara pemeriksaan khusus review_report bersih. Model/migrasi profil tidak diubah oleh modul ini. Warning staticfiles belum ada dapat muncul sebelum collectstatic; bukan kegagalan test.

Hasil final pada 28 Oktober 2026:

- Suite gabungan dengan `RUN_BROWSER_TESTS=1`: **132 tests, OK, tanpa skip**, 103,929 detik. Terdiri dari 83 tests bawaan dan 49 tests modul (termasuk 3 Selenium).
- Coverage kode modul: **99%** (484 statements, 4 belum tercakup; 82 branches, 1 cabang parsial). Tests/migrasi tidak masuk denominator. Services dan views 100%, admin 93%.
- Screenshot desktop, tablet 768 px, dan ponsel 390 px sudah dibaca secara visual; tidak ada scroll horizontal pada ukuran yang diuji. Semua ikon desain yang digunakan tersedia lokal, nonempty, dan ukuran rendernya sesuai metadata SVG.
- `check`: tidak ada masalah. `makemigrations review_report --check --dry-run`: bersih. Kedua migrasi modul berhasil diterapkan ke database lokal; database lokal tidak di-commit.
- Tidak ada push, merge main, atau deploy. Syarat penyelesaian transaksi melalui UI katalog tetap bergantung pada branch Owen sebagaimana dijelaskan di atas.
