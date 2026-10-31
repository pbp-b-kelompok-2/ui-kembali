# ♻️ UIKembali
A web platform for UI students to give away or sell reusable second-hand items, making it easier to find affordable goods while reducing waste and extending product lifecycles.

---

## 👥 Anggota Kelompok

| Nama | NPM |
|---|---|
| Axel Sebastian Saragih | 2506590063 |
| Dimas Bayu Nugroho | 2506534636 |
| Elvis Sestomi | 2506544990 |
| Muhammad Rifky Padjri | 2506585800 |
| Owen Viriya Chandra | 2506539196 |


---

## 📦 Modul Aplikasi

| No. | Nama Modul | Deskripsi | Anggota |
|---|---|---|---|
| 1 | **Profile** | Menangani autentikasi pengguna yang terintegrasi dengan **SSO UI**, serta pengelolaan data profil pengguna seperti nama, fakultas, angkatan, foto profil, dan informasi lainnya. | **Elvis** |
| 2 | **Posting & Katalog Barang** | Menangani CRUD posting barang yang ingin diberikan atau dijual, termasuk nama, deskripsi, kategori, kondisi, foto, lokasi, jenis transaksi (adopsi/jual), dan harga. Modul ini juga menyediakan katalog, pencarian, filter, halaman detail barang, serta pengelolaan permintaan adopsi atau pembelian. | **Owen** |
| 3 | **Chat** | Menangani komunikasi antar pengguna, khususnya antara pemilik/penjual dengan calon pengadopsi/pembeli. Modul mencakup pembuatan percakapan, pengiriman pesan, dan pengelolaan pesan. | **Axel** |
| 4 | **Forum** | Menyediakan ruang diskusi bagi pengguna untuk berbagi informasi, pengalaman, tips, dan pertanyaan seputar barang bekas, kehidupan kost, serta penggunaan kembali barang. Modul mencakup CRUD posting forum dan interaksi pengguna pada forum. | **Dimas** |
| 5 | **Review & Report** | Menangani pemberian rating dan ulasan setelah proses adopsi atau pembelian selesai, serta pelaporan terhadap barang atau pengguna yang bermasalah. | **Padjri** |

---

## 📝 Detail Modul

### Modul 1 — Profile

**Penanggung jawab:** Elvis Sestomi  
**Model utama:** `Profile`  
**Integrasi eksternal:** UI SSO melalui CAS

Modul ini mengelola autentikasi pengguna lewat UI SSO dan data profil yang dibutuhkan untuk memakai UIKembali, mulai dari login pertama sampai pengeditan profil.

#### Fitur

- Login melalui UI SSO. Saat ingin login, aplikasi membatasi pengguna untuk melakukan login hanya melalui SSO UI, dan akan di-redirect ke pengisian profil awal untuk kasus login pertama kali.
- Pengisian profil awal. Pengguna dengan profil yang belum lengkap otomatis diarahkan ke halaman pengisian profil dan belum dapat mengakses fitur yang memerlukan profil lengkap.
- Halaman profil memungkinkan pengguna untuk melakukan pengeditan nama panggilan, nomor WhatsApp, foto profil, titik temu favorit, dan bio.
- Halaman profil menampilkan identitas pengguna, ringkasan ulasan, tautan ke ulasan dan laporan, serta display tiga transaksi terbaru.
- Pengeditan profil memakai HTMX, sehingga formulir diperbarui tanpa memuat ulang seluruh halaman.
- Upload foto profil hanya mengizinkan JPG, PNG, atau WEBP (maksimal 2 MB). Gambar kemudian diubah menjadi WEBP.

#### Keamanan

- Field nama, fakultas, dan angkatan yang berasal dari SSO dinonaktifkan pada formulir, sehingga tidak dapat diubah lewat formulir profil.
- Nomor WhatsApp dan tahun angkatan divalidasi oleh validator pada model.
- Akun yang dibuat hanya dapat diakses kembali dengan melakukan login melalui SSO UI.

#### Integrasi UI SSO

- UI SSO mengirimkan username dan atribut pengguna ke aplikasi melalui CAS.
- Aplikasi menyimpan username, lalu menyinkronkan nama, fakultas, dan angkatan dari atribut `npm` yang diterima dari API SSO.

#### Pengujian

Modul yang diuji dengan unit test mencakup:

- model dan formulir,
- decorator akses,
- pengisian dan pengeditan profil,
- halaman profil,
- URL.

```bash
python manage.py test auth_ssoui
```

### Modul 2 — Posting & Katalog Barang

**Penanggung jawab:** Owen Viriya Chandra  
**Model utama:** `Item`, `ItemRequest`  
**Public API:** OpenStreetMap (Nominatim dan tile peta melalui Leaflet)

Modul ini menjadi pusat katalog barang bekas yang diberikan atau dijual oleh mahasiswa UI, sekaligus mengatur alur permintaan barang dari pengajuan sampai serah terima.

#### Fitur

- CRUD barang melalui modal tanpa memuat ulang halaman, dengan data nama, deskripsi, kategori, kondisi, foto, lokasi temu, jenis penawaran (adopsi/jual), harga, dan kontak.
- Upload foto JPG, PNG, atau WEBP (maksimal 5 MB). Foto diperkecil, disimpan sebagai WEBP, dan metadata EXIF-nya dihapus.
- Validasi form: panjang minimum nama dan deskripsi, penghapusan tag HTML, serta aturan harga (wajib untuk barang dijual, kosong untuk barang adopsi).
- Halaman katalog dengan 52 data barang awal, pagination, dan halaman detail barang.
- Pencarian langsung, filter kategori, kondisi, jenis penawaran, lokasi, dan rentang harga, serta pengurutan hasil.
- Soft delete dengan tombol urungkan, dan halaman "Barang saya" dengan aksi massal (hapus, tandai selesai, kembalikan).
- Pengajuan adopsi atau pembelian dengan status **Menunggu → Diterima → Selesai**, atau **Ditolak** dan **Dibatalkan**.
- Pusat permintaan untuk melihat permintaan masuk dan keluar. Saat satu permintaan diterima, permintaan lain untuk barang yang sama otomatis ditolak.
- Endpoint JSON untuk daftar barang (`/katalog/json/`) dan detail barang (`/katalog/<id>/json/`).

#### Keamanan

- Hanya pemilik yang dapat mengubah atau menghapus barangnya. Pengguna lain mendapat respons 403.
- Kontak pemilik dan titik lokasi yang tepat hanya tampil untuk pengguna yang sudah login. Tamu hanya melihat area perkiraan.
- Rate limit 10 aksi per menit untuk membuat barang, mengajukan permintaan, dan aksi massal.

#### Pemanfaatan Public API

- **Nominatim (OpenStreetMap)** mengubah nama lokasi temu menjadi koordinat saat barang disimpan. Hasilnya di-cache selama 30 hari. Jika layanan tidak tersedia, aplikasi memakai daftar tempat di sekitar kampus UI, dan barang tetap tersimpan walaupun lokasinya tidak ditemukan.
- **Leaflet dan OpenStreetMap** menampilkan lokasi barang pada peta di halaman detail.
- Koordinat tersebut dipakai untuk filter radius (1, 2, 5, atau 10 km) dan pengurutan berdasarkan jarak terdekat.

#### Pengujian

Modul diuji dengan unit test untuk model, form, view, dan geocoding (API dimock), serta functional test Selenium:

```bash
python manage.py test katalog --exclude-tag=functional
python manage.py test katalog.tests.test_functional
```


### Modul 3 — Chat

- **Penanggung jawab:** Axel Sebastian Saragih
- **Model utama:** `Conversation`, `Message`

Modul ini menyediakan komunikasi langsung antara pemilik barang dan calon pengadopsi atau pembeli untuk membahas segala hal mengenai transaksi.

#### Fitur

- Percakapan dapat dimulai dari halaman barang. Satu calon pembeli hanya memiliki satu percakapan untuk setiap barang; percakapan yang sudah ada akan digunakan kembali.
- Inbox menampilkan daftar percakapan, nama barang, pratinjau pesan terakhir, dan jumlah percakapan.
- Pencarian percakapan berdasarkan nama barang atau username peserta.
- Pesan dikirim tanpa memuat ulang halaman dan diperbarui otomatis setiap 3 detik (3000 ms).
- Status pesan masuk diperbarui menjadi telah dibaca saat percakapan dibuka atau pesannya dimuat dan isi pesan wajib diisi, dibatasi maksimal 2.000 karakter.

#### Keamanan

- Pengguna harus login untuk membuka inbox, memulai percakapan, atau mengirim pesan.
- Hanya pemilik barang dan calon pembeli yang menjadi peserta percakapan yang dapat membaca atau mengirim pesan.
- Pemilik barang tidak dapat memulai percakapan dengan dirinya sendiri.

#### Pengujian

Modul diuji dengan unit test untuk model percakapan dan pesan, serta view terkait autentikasi, pembuatan percakapan, validasi, dan akses peserta:

```bash
python manage.py test chat
```


### Modul 4 — Forum

**Penanggung jawab:** Dimas Bayu Nugroho  
**Model utama:** `ForumPost`, `ForumAttachment`, `Comment`  
**Public API:** Tidak menggunakan public API eksternal

Modul Forum menyediakan ruang bagi pengguna untuk berbagi diskusi, bertanya, dan bertukar pengalaman seputar barang bekas serta kehidupan kampus.

#### Fitur

- CRUD posting forum dengan judul, isi, dan kategori **Tips**, **Tanya**, **Pengalaman**, atau **Lainnya**.
- Upload satu atau beberapa lampiran pada posting, melihat lampiran, dan menghapus lampiran dari posting milik sendiri.
- Daftar posting dengan pencarian berdasarkan judul atau isi, filter kategori, filter posting milik sendiri atau tersimpan, pengurutan terbaru/terlama/populer, dan pagination.
- Halaman detail posting dengan komentar dan balasan bertingkat, pengurutan komentar, serta daftar posting terkait.
- Like posting dan komentar, serta simpan atau batal-simpan posting.

#### Keamanan

- Membuat posting, berkomentar, memberi like, dan menyimpan posting memerlukan login.
- Hanya pemilik posting yang dapat mengubah atau menghapus posting dan lampirannya.
- Aksi yang mengubah data menggunakan metode POST; redirect setelah aksi like/simpan dibatasi ke host aplikasi.

#### Pengujian

Test mencakup pencarian, filter, pengurutan, pagination, CRUD posting, unggah dan penghapusan lampiran, komentar dan balasan, like, simpan posting, serta pemeriksaan login dan kepemilikan.

Jalankan seluruh test modul Forum dengan:

```bash
python manage.py test forum
```

### Modul 5 — Review & Report

**Proyek:** UIKembali

**Penanggung jawab:** Muhammad Rifky Padjri — 2506585800

**Model utama:** `Review`, `Report`, `ReportSubmission`

**Relasi modul:** `katalog.ItemRequest`, `katalog.Item`, dan `settings.AUTH_USER_MODEL`

**Antarmuka:** Django Template, Tailwind CSS, dan HTMX

Modul ini memungkinkan pengadopsi atau pembeli memberikan ulasan setelah transaksi
selesai, serta melaporkan barang atau pengguna yang bermasalah. Ulasan menjadi
informasi reputasi publik, sedangkan laporan ditangani secara privat oleh petugas
berizin.

#### Fitur

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
- Layout responsif menggunakan Tailwind CSS 4.1.13 tanpa preflight, mewarisi
  `base.html` melalui `base_review_report.html`.

#### Keamanan dan aturan akses

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


#### Pengujian

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
memerlukan Chrome serta akses ke CDN yang dipakai antarmuka. 

---

## 👤 Jenis dan Peran Pengguna

UIKembali memiliki satu jenis pengguna utama, yaitu **User**. Setiap pengguna dapat menjalankan dua peran sekaligus, yaitu sebagai **Pemilik/Penjual** dan **Pengadopsi/Pembeli**.

### Pemilik/Penjual

Pengguna sebagai pemilik atau penjual dapat:

- Membuat posting barang.
- Mengubah dan menghapus posting barang.
- Menentukan apakah barang dapat **diadopsi secara gratis** atau **dibeli**.
- Menentukan harga apabila barang dijual.
- Menerima atau menolak permintaan transaksi.
- Berkomunikasi dengan calon pengadopsi atau pembeli melalui fitur chat.
- Menerima review setelah transaksi selesai.

### Pengadopsi/Pembeli

Pengguna sebagai pengadopsi atau pembeli dapat:

- Melihat katalog barang yang tersedia.
- Mencari dan memfilter barang berdasarkan kategori, kondisi, jenis transaksi, dan lokasi.
- Mengajukan adopsi barang secara gratis.
- Mengajukan pembelian barang.
- Berkomunikasi dengan pemilik barang melalui fitur chat.
- Memberikan review dan rating setelah transaksi selesai.
- Melaporkan barang atau pengguna yang bermasalah.

> Satu akun dapat berperan sebagai pemilik/penjual maupun pengadopsi/pembeli.

---

## 🌐 Public API

### OpenStreetMap

UIKembali menggunakan **OpenStreetMap** untuk menyediakan informasi lokasi barang dan menampilkan lokasi barang pada peta.

Penggunaan API meliputi:

- Menentukan lokasi barang.
- Menampilkan lokasi barang pada peta.
- Membantu pengguna mengetahui lokasi barang yang ingin diadopsi atau dibeli.
- Mendukung fitur pencarian barang berdasarkan lokasi.

**Dokumentasi:**  
https://wiki.openstreetmap.org/wiki/API

### UI SSO

UIKembali menggunakan **UI SSO** sebagai mekanisme autentikasi pengguna. Dengan autentikasi ini, pengguna dapat masuk ke dalam aplikasi menggunakan akun Universitas Indonesia.

**Dokumentasi:**  
- as reference : https://github.com/RistekCSUI/django-sso-ui
- rebuild in file : ./auth_ssoui/sso_compat.py

---

## 🎨 Desain Figma

Desain antarmuka UIKembali dibuat menggunakan Figma.

**Figma:**  
[LINK](https://www.figma.com/design/rTVD1SeON4Oi2QX6KCMLmN/UIKembali?node-id=0-1&p=f&t=z9WZO9P8ZcTj0RiZ-0)

---

## 🚀 Deployment

Aplikasi UIKembali telah di-deploy menggunakan PWS.

**PWS:**  
[LINK](https://elvis-sestomi-ui-kembali.pws.cs.ui.ac.id/)


---

## 🔄 Alur Utama Aplikasi

Secara umum, alur penggunaan UIKembali adalah sebagai berikut:

1. Pengguna masuk menggunakan UI SSO.
2. Pengguna dapat melihat dan mengubah profil.
3. Pengguna dapat melihat katalog barang yang tersedia.
4. Pengguna dapat mencari dan memfilter barang berdasarkan kebutuhan.
5. Pengguna memilih salah satu barang.
6. Pengguna dapat:
   - mengajukan **adopsi** jika barang diberikan secara gratis, atau
   - mengajukan **pembelian** jika barang dijual.
7. Pemilik menerima atau menolak permintaan transaksi.
8. Pemilik dan calon pengadopsi/pembeli dapat berkomunikasi melalui chat.
9. Setelah transaksi selesai, pengguna dapat memberikan review dan rating.
10. Pengguna dapat melaporkan barang atau akun yang dianggap bermasalah.

---

## 🤖 AI Disclosure

### Modul 1 — Profile (Elvis)

- **Tool:** Codex (gpt-6-luna).
- **Penggunaan:** perencanaan, pembangunan page html, penulisan kode dan test, refactor, serta debugging error. Preferensi fitur dipilih oleh saya dan beberapa kode awal masih ditulis oleh saya.
- **Perbaikan:** build tahun angkatan berdasarkan NPM, pengolahan awal response json dari API SSO, routing url dan pembangunan awal view function, dan penyederhanaan kode agar lebih mudah dibaca.
- **Kekurangan:** belum terdapat response terhadap interaksi user dengan display 3 riwayat terbaru pada tampilan page profile. beberapa view function berujung tidak terpakai dikarenakan terdapat duplikasi pada routing lain aplikasi. beberapa style page masih belum konsisten dengan page lainnya dalam aplikasi.


### Modul 2 — Posting & Katalog Barang (Owen)

- **Tool:** Claude Code (Anthropic).
- **Penggunaan:** perencanaan, penulisan kode dan test (Red-Green-Refactor), refactor, serta debugging. Keputusan fitur tetap dari saya, dan hasilnya saya periksa lewat diff, test, dan browser.
- **Perbaikan manual:** test urutan yang tidak stabil karena timestamp sama, pembulatan koordinat untuk tamu, dan penyederhanaan kode agar lebih mudah dibaca.
- **Keterbatasan:** versi awal upload foto belum menolak gambar beresolusi sangat besar, bug URL form Edit lolos dari test dan baru terlihat saat dicoba langsung, dan masalah di PWS baru ketahuan setelah deploy.


### Modul 3 — Chat (Axel)

- **Tool:** GitHub Copilot (gpt-6-luna).
- **Penggunaan:** Penulisan kode dan test (Red-Green-Refactor), refactor, serta debugging. Membantu menyusun dokumentasi Modul 3 berdasarkan implementasi yang ada, disertai berbagai revisi.
- **Revisi:** Background color bubble messages beserta ukurannya tidak sesuai sehingga saya perbaiki. Tulisan "Dibaca" pada pesan juga awalnya salah posisi tetapi sudah dibetulkan. Semua keputusan fitur berasal dari saya beserta rembukan kelompok.
- **Keterbatasan:** Kurang polish: scrollbar pada aplikasi chat umumnya hanya di container chat, bukan keseluruhan halaman.


### Modul 4 - Forum (Dimas)

- **Tool:** Codex (OpenAI, gpt-6-luna).
- **Penggunaan:** membantu perencanaan dan implementasi fitur forum, penulisan serta perbaikan test, refactor, dan debugging. Cakupan fitur forum meliputi CRUD posting dan lampiran, pencarian/filter/pengurutan, komentar bertingkat, like, dan simpan posting.
- **Perbaikan manual:** keputusan fitur dan penyesuaian akhir tetap saya lakukan. Saya meninjau perubahan kode dan hasil test agar sesuai kebutuhan project.
- **Keterbatasan:** test otomatis mencakup banyak perilaku backend, tetapi belum membuktikan semua variasi tampilan, browser, dan unggahan file di penggunaan nyata; pemeriksaan manual tetap diperlukan.

### Modul 5 - Review Report (Padjri)
- **Tool:** Codex (OpenAI, gpt-6.1-sol).
- **Penggunaan:** membantu perencanaan, implementasi model/form/services/view/template,
  dan penulisan test.
- **Perbaikan selama pengembangan:** penanganan error validasi model pada form,
  resolusi target laporan, URL tujuan setelah swap HTMX, indikator menyimpan,
  serta navigasi dan layout responsif.
- **Batas verifikasi:** pengujian lokal menggunakan SQLite; locking konkuren pada
  PostgreSQL dan autentikasi SSO sungguhan belum dibuktikan oleh test lokal tersebut.
  Test browser mencakup skenario yang ditulis, bukan seluruh kombinasi perangkat.

