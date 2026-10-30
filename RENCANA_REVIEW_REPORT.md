# Rencana Modul Review & Report — UIKembali

Tanggal audit: 27 Oktober 2026. Penanggung jawab: Muhammad Rifky Padjri.

Dokumen ini adalah rencana implementasi, bukan perubahan fitur. Persyaratan dari PDF diperlakukan sebagai bahan analisis tugas; rekomendasi produk dan teknis di bawah adalah usulan yang dibedakan dari persyaratan tersebut.

## 1. Sumber dan batas audit

- Seluruh empat halaman `C:/Users/ACER/Downloads/midterm.pdf` dibaca.
- README, struktur aplikasi Django, model, autentikasi, URL, template dasar, pola HTMX/toast, dan contoh pengujian ditinjau dari checkout lokal.
- `git fetch origin` berhasil. HEAD lokal dan `origin/main` sama-sama `46e4b159413f09b740f5eed72cb4442c2bfcd759` pada saat audit.
- Seluruh tujuh branch remote yang tersedia dipetakan melalui riwayat commit dan perbedaan berkas. Kode integrasi transaksi, profil, dan geocoding dibaca secara terarah. Ini bukan audit baris demi baris seluruh kode atau hasil pengujian runtime seluruh branch.
- Figma `rTVD1SeON4Oi2QX6KCMLmN`, halaman `0:1`, dibaca melalui metadata. Terdapat struktur halaman `20:11438`, “10 · Penyelesaian review dan laporan”, beserta desain profil, riwayat transaksi, dan design system. Metadata membuktikan struktur komponen; kesetiaan visual rinci perlu diperiksa saat implementasi.
- Tidak ada BRP/rubrik rinci atau akses SCELE yang disediakan. Bobot penilaian individu tidak diasumsikan.
- Tidak ada branch chat Axel pada daftar remote saat audit. Pada snapshot branch Dimas tidak ditemukan implementasi app forum. Ini tidak membuktikan bahwa pekerjaan mereka belum ada secara lokal.
- Aplikasi tidak dijalankan dan test suite tidak dijalankan dalam audit perencanaan ini. Keberadaan test tidak berarti test sudah lulus.

## 2. Persyaratan tugas yang perlu dipenuhi

| Ketentuan PDF | Bukti yang harus tersedia dari modul Padjri |
| --- | --- |
| Satu modul dengan CRUD lengkap | Review dapat dibuat, dibaca, diubah, dan dihapus lewat antarmuka pengguna |
| Model, View, Template, dan Form | App Django dengan model, validasi, URL, halaman dan form yang benar-benar terhubung |
| Framework CSS responsif | Halaman review/report mengikuti kerangka bersama dan nyaman di ponsel |
| AJAX/HTMX | Kirim/edit/hapus ulasan dan filter daftar tanpa memuat ulang seluruh halaman |
| Pembatasan berdasarkan autentikasi | Hak menulis ulasan, akses laporan pribadi, dan akses moderasi diperiksa di server |
| Filter data dari Public API/mock API/database | Sediakan filter rating, jenis transaksi, kategori barang, dan status laporan; klarifikasi cakupan ketentuan Public API per anggota dengan asdos |
| Unit test | Uji aturan bisnis, otorisasi, validasi, tampilan, dan integrasi |
| Integrasi dan deployment | Semua URL, migrasi, static files, dan alur bekerja pada aplikasi gabungan di PWS |

Ketentuan kelompok: integrasi Public API eksternal, desain/wireframe, satu repositori, README lengkap, dan sedikitnya 50 data utama pada deployment. Untuk marketplace ini, rencanakan sedikitnya 50 barang tersedia; jangan menganggap 50 ulasan atau 50 laporan menggantikan kebutuhan tersebut.

PDF menyarankan coverage minimal 80%; kalimatnya merupakan rekomendasi, bukan batas wajib yang dinyatakan tegas. Jadikan >=80% untuk modul ini sebagai target internal, sambil mengutamakan kasus bisnis penting.

Tenggat final pada PDF: Jumat, 30 Oktober 2026 pukul 23.59 WIB. Pada tanggal audit, jendela kerja yang tersedia adalah 27–30 Oktober; konfirmasi pengumuman terbaru bila ada perubahan resmi.

## 3. Peta branch dan keputusan integrasi

| Branch | Temuan | Implikasi |
| --- | --- | --- |
| `main` | SSO/profil dan katalog; `Item` dan `ItemRequest` sudah ada | Titik awal pekerjaan baru; app review/report belum ditemukan |
| `chore/base-setup` | Pendahulu kode yang telah masuk ke main | Tidak perlu digabung ulang |
| `feat/dimas` | Tidak memiliki commit unik terhadap main; snapshot fondasi lama | Jangan menyalin template lama sebagai basis modul |
| `feat/owen-katalog` | Tidak memiliki commit unik terhadap main | Fondasi katalog sudah tersedia |
| `feat/owen-requests` | `katalog/services.py`, pusat permintaan, complete/cancel/accept/reject, bulk actions | Dependensi utama alur pemberian review |
| `feat/owen-osm` | Memuat commit request lifecycle dan tambahan Nominatim/peta/filter radius | Pertimbangkan integrasi branch ini sebagai kelanjutan Owen; tidak perlu menggabungkan dua branch Owen secara serampangan |
| `feat/vis` | Tailwind profil, template dasar profil, komponen foto profil, tiga transaksi terbaru, test autentikasi | Koordinasi dengan Elvis untuk ringkasan rating dan tautan riwayat/review |

`complete_request(req, user)` pada branch Owen mengubah `ItemRequest.status` dan `Item.status` menjadi `SELESAI`. Komentarnya secara eksplisit menyebut bahwa modul review Padjri menggunakan status ini. Pada main saat audit, layanan tersebut belum ada dan panel pengajuan detail masih placeholder.

`mark_items_done()` juga dapat menandai barang selesai tanpa adanya request diterima. Karena itu `Item.status == SELESAI` saja tidak cukup sebagai bukti bahwa seseorang boleh memberi ulasan.

Urutan yang disarankan:

1. Buat branch fitur dari main terkini, misalnya `codex/padjri-review-report`.
2. Sepakati dengan Owen commit request lifecycle yang akan dipakai. Usahakan perubahan Owen masuk main lebih dahulu, atau gunakan basis integrasi yang disepakati kelompok.
3. Kembangkan mayoritas kode pada app sendiri, misalnya `review_report`.
4. Setelah dependensi masuk main, perbarui branch fitur dan selesaikan konflik terarah.
5. Hindari menyalin seluruh folder katalog/profil dari branch lain: snapshot lama dapat membawa versi template dan autentikasi yang tertinggal.
6. Integrasikan melalui PR dengan bukti uji dan demonstrasi alur lengkap.

## 4. Cakupan produk yang direkomendasikan

### Prioritas P0 — selesai sebelum mempercantik fitur tambahan

Review:

- Rating bilangan bulat 1–5 dan ulasan teks.
- Hanya pengadopsi/pembeli pada `ItemRequest` selesai yang dapat menilai pemilik/penjual dari transaksi tersebut.
- Satu review per transaksi. Larang ulasan diri sendiri dan ulasan transaksi orang lain.
- CRUD lengkap oleh penulis review; penerima tidak boleh mengubah atau menghapus review penulis.
- Daftar “Ulasan saya” dan daftar ulasan untuk pemilik/penjual dengan pagination/filter.
- Rata-rata rating dan jumlah review dihitung dari review yang masih aktif; kondisi nol review ditampilkan sebagai “Belum ada ulasan”.

Report:

- Pelaporan barang atau pengguna, dengan kategori dan uraian masalah.
- Tidak harus menunggu transaksi selesai: barang mencurigakan perlu bisa dilaporkan sebelum pengajuan.
- “Laporan saya” dan detail laporan bersifat privat.
- Pengguna dapat membuat, membaca, mengubah, dan menghapus laporan miliknya selama masih menunggu pemeriksaan.
- Petugas yang diberi izin dapat meninjau dan mengubah status melalui Django admin sebagai cakupan awal.
- Isi laporan tidak ditampilkan sebagai reputasi publik dan tidak memicu hukuman otomatis.

Moderasi melalui Django admin adalah usulan implementasi. README saat audit mendefinisikan satu jenis pengguna utama; akun staff adalah kewenangan operasional terbatas yang perlu disepakati dan didokumentasikan kelompok, bukan otomatis peran bisnis baru.

### Prioritas P1 — setelah P0 terintegrasi dan lulus uji

- Tag ulasan sebagaimana struktur Figma, misalnya komunikasi baik atau barang sesuai deskripsi; gunakan daftar tag yang disepakati.
- Distribusi bintang, ringkasan rating di kartu penjual, dan detail reputasi.
- Filter kategori/jenis transaksi serta integrasi filter lokasi bila dibutuhkan.
- Lampiran bukti jika waktu cukup, lengkap dengan validasi dan akses privat; jangan menganggap direktori media publik sudah aman untuk bukti laporan.
- JSON read endpoints yang memakai aturan akses sama, sebagai persiapan Flutter. API tulis lengkap mengikuti kebutuhan tahap akhir semester, kecuali diminta pada rubrik lain.

Tunda chat real-time baru, AI moderation, notifikasi email, mekanisme banding kompleks, dan pemblokiran otomatis. Kualitas P0 dan integrasi lebih bernilai daripada banyak fitur setengah selesai.

## 5. Aturan bisnis dan model data usulan

### Review

Field inti:

- `id`: UUID.
- `item_request`: OneToOne ke `katalog.ItemRequest`; satu review per request.
- `rating`: integer 1–5, dengan validator dan database check constraint.
- `comment`: teks wajib, batas panjang ditentukan bersama, misalnya 10–1000 karakter.
- `created_at`, `updated_at`.

Penulis dan penerima dapat diturunkan dari `item_request.requester` dan `item_request.item.owner`. Ini mengurangi peluang data penulis/penerima bertentangan dengan transaksi. Jika nanti perlu menyimpan keduanya secara eksplisit untuk audit atau performa, isi hanya di server dan pastikan konsisten.

Sebelum simpan, server memeriksa:

1. Sudah login; terapkan syarat profil lengkap bila menjadi kebijakan bersama.
2. `request.user.pk == item_request.requester_id`.
3. `item_request.status == ItemRequest.Status.SELESAI`.
4. Requester berbeda dari owner.
5. Review transaksi tersebut belum ada; constraint tetap menangani dua pengiriman bersamaan.
6. Rating dan teks valid.

Saat edit/hapus, ambil objek dari queryset milik pengguna. Jangan hanya menyembunyikan tombol. Gunakan transaksi database dan tangani konflik duplikasi dengan pesan yang jelas.

Pilihan awal yang sederhana: hapus review secara nyata dan izinkan penulis membuat ulang satu review untuk request tersebut. Setelah delete, agregat rating harus berubah. Jika memilih soft-delete, tentukan kebijakan pemulihan dan uniqueness sejak awal agar satu transaksi tidak punya dua review aktif.

### Report

Field inti:

- `id`: UUID.
- `reporter`: FK ke `settings.AUTH_USER_MODEL`.
- `target_item`: nullable FK ke `katalog.Item`.
- `target_user`: nullable FK ke `settings.AUTH_USER_MODEL`.
- `category`: pilihan alasan yang jelas, misalnya penipuan, barang terlarang, deskripsi menyesatkan, pelecehan, spam, lainnya.
- `description`: uraian wajib dengan panjang terbatas.
- `status`: `PENDING`, `IN_REVIEW`, `RESOLVED`, atau `REJECTED`.
- `created_at`, `updated_at`, `reviewed_at`, dan `reviewed_by` bila dipakai untuk audit.
- Catatan internal petugas dipisahkan dari pesan hasil yang boleh dilihat pelapor.

Constraint penting: tepat satu target terisi. Dua target terisi atau keduanya kosong harus ditolak pada form, layanan, dan constraint database.

Pelapor berasal dari sesi login. Status dan identitas petugas tidak termasuk field form pengguna. Larang pelaporan diri sendiri; larangan pelaporan barang sendiri juga disarankan dan perlu dinyatakan sebagai kebijakan produk.

Alur status: `PENDING -> IN_REVIEW -> RESOLVED / REJECTED`. Hanya `PENDING` boleh diedit/dihapus pelapor; setelah pemeriksaan dimulai tampilkan alasan penguncian. Staff mengubah status dan mencatat penanganan. Uji transisi yang tidak sah.

Batasi spam dengan rate limit dan pencegahan laporan aktif duplikat dari pelapor ke target yang sama. Untuk laporan yang sudah ditutup, tentukan apakah kasus baru boleh dilaporkan; rekomendasi: boleh, dengan uraian baru. Jangan memaksa unique seumur hidup.

### Retensi dan barang yang dihapus

`Item.objects` menyembunyikan barang soft-delete, sedangkan `Item.all_objects` tetap dapat menemukannya. Ulasan/riwayat dan laporan yang sudah ada perlu tetap dapat dibaca oleh pihak yang berhak meskipun barang disembunyikan. Hindari detail publik barang terhapus menjadi terbuka hanya karena laporan memakai `all_objects`.

Usulan `on_delete`: lindungi request yang sudah memiliki review dengan `PROTECT`; pertimbangkan `PROTECT` untuk target laporan juga. Karena `ItemRequest.item` saat ini `CASCADE`, hard-delete Item dapat terhalang oleh review. Sepakati dampaknya bersama Owen/Elvis. Kebijakan penghapusan akun juga perlu ditetapkan; jangan mengklaim perlindungan audit lengkap bila rantai FK lain masih menghapus data.

## 6. Halaman dan integrasi UI

Figma acuan: https://www.figma.com/design/rTVD1SeON4Oi2QX6KCMLmN/UIKembali?node-id=20-11438

Struktur yang sudah tersedia pada desain: ringkasan transaksi, formulir bintang, pilihan tag, teks ulasan, aksi kirim/lewati, pilihan laporkan barang/pengguna, dan panel aftercare. Gunakan data nyata dan jangan menampilkan angka dampak lingkungan sebagai hasil terukur tanpa dasar perhitungan.

Halaman minimum:

1. Penyelesaian transaksi/review: dapat diakses dari transaksi selesai; pengguna yang tidak berhak memperoleh respons akses yang sesuai.
2. Ulasan saya: daftar, filter rating/jenis transaksi, edit/hapus.
3. Ulasan pemilik: daftar ulasan yang diterima dan ringkasan rating. Bila profil publik belum tersedia, buat halaman ulasan sendiri lalu tautkan dari detail barang.
4. Form report barang/pengguna: target otomatis dari URL, kategori dan deskripsi.
5. Laporan saya: daftar status, detail, edit/hapus untuk yang masih menunggu.
6. Django admin report: daftar, filter status/kategori, detail, dan penanganan.

Usulan pola URL, bukan endpoint yang sudah ada:

| URL | Tujuan |
| --- | --- |
| `/review-report/transaksi/<uuid>/` | Halaman review untuk satu request |
| `/review-report/ulasan/saya/` | Review yang ditulis pengguna |
| `/review-report/pengguna/<id>/ulasan/` | Review yang diterima pemilik |
| `/review-report/ulasan/<uuid>/edit/` | Form dan proses update |
| `/review-report/ulasan/<uuid>/hapus/` | Delete lewat POST |
| `/review-report/laporkan/barang/<uuid>/` | Create laporan barang |
| `/review-report/laporkan/pengguna/<id>/` | Create laporan pengguna |
| `/review-report/laporan/saya/` | Daftar laporan privat |
| `/review-report/laporan/<uuid>/` | Detail privat |
| `/review-report/laporan/<uuid>/edit/` | Edit laporan pending |
| `/review-report/laporan/<uuid>/hapus/` | Delete laporan pending lewat POST |

Pakai tipe ID User sesuai model auth aktual; jangan menganggap semua ID adalah UUID. Create/update dapat menerima GET untuk form dan POST untuk perubahan. GET tidak boleh menghapus data atau mengubah status.

Integrasi milik anggota lain:

- Owen: tombol “Beri ulasan” pada request selesai milik requester; tombol “Lihat/Edit ulasan” setelah review ada. Tambahkan tautan laporkan barang dan laporkan pemilik pada detail barang.
- Elvis: rating rata-rata, jumlah ulasan, tautan ulasan/laporan saya, serta aksi review dari riwayat transaksi. Profil publik belum memiliki endpoint pada URL profil yang ditinjau, sehingga jangan mengandalkannya sebelum disepakati.
- Axel: tautan report dari chat dapat menyusul jika endpoint konteks chat tersedia. P0 report pengguna tetap bisa dipakai dari detail barang.
- Kelompok: navigasi nyata menggantikan placeholder yang relevan, serta dokumentasi kewenangan staff.

Responsif: tiga kolom pada desktop menjadi satu kolom pada ponsel, tombol mudah ditekan, form berlabel, rating memakai radio input dengan label sehingga keyboard dapat digunakan. Tampilkan kondisi belum ada data, sedang menyimpan, validasi gagal, sukses, dan akses ditolak.

Katalog memakai Tailwind browser v4 tanpa preflight, sementara base profil branch Elvis memakai konfigurasi Tailwind CDN berbeda dan font berbeda. Root CSS juga mempunyai token bersama. Sepakati satu pendekatan untuk app baru; jangan memuat dua runtime Tailwind pada halaman yang sama. Buat `base_review_report.html` yang mewarisi `base.html` dan menjaga navbar/footer.

Gunakan pola HTMX, CSRF, dan toast yang sudah ada. Respons validasi 422 tidak otomatis ditukar oleh semua konfigurasi HTMX: bila memakai 422, pastikan handler pertukaran form error benar-benar bekerja. Alternatifnya kembalikan partial form dengan status yang ditangani secara konsisten. Uji login kedaluwarsa agar halaman SSO tidak muncul di dalam modal.

## 7. Public API dan filter: keputusan yang perlu dikunci

Kelompok sudah merencanakan OpenStreetMap. Branch Owen menunjukkan integrasi Nominatim, cache, fallback titik kampus, peta, dan filter radius; README masih menautkan dokumentasi API OSM umum. Dokumentasikan API yang benar-benar dipakai dan tunjukkan panggilan eksternal yang berhasil, bukan hanya fallback statis.

Untuk modul ini, sediakan filter database rating, kategori barang, jenis transaksi, dan status laporan. Namun, kalimat syarat filter pada bagian per anggota dapat ditafsirkan sebagai kebutuhan kaitan langsung dengan data Public API. Karena rubrik rinci tidak tersedia, klarifikasi singkat dengan asdos apakah filter database modul memenuhi ketentuan tersebut.

Jika harus ada kaitan langsung, gunakan integrasi yang relevan dan sudah ada: filter ulasan berdasarkan lokasi barang yang digeocode Nominatim atau radius dari titik kampus, dengan fungsi geocoding Owen dan pengujian mock. Filter kategori saja tidak boleh disebut sebagai pemfilteran respons API eksternal. Jangan menambah API yang tidak relevan sekadar untuk demonstrasi.

## 8. Struktur kode yang disarankan

App `review_report/`: `models.py`, `forms.py`, `services.py`, `views.py`, `urls.py`, `admin.py`, `migrations/`, `templates/review_report/`, dan `tests/`.

Simpan aturan hak review, duplikasi, target report, dan perubahan status di layanan yang dipakai seluruh entry point. Form bertugas memvalidasi input; constraint database menjaga invariant yang dapat dinyatakan di database. Tambahkan app ke `INSTALLED_APPS` dan URL proyek. Gunakan relasi string untuk model lintas app bila perlu menghindari circular import.

Agregasi rating memakai `Avg` dan `Count` dari data review aktif. Daftar memakai pagination dan `select_related` yang sesuai. Jangan menyimpan rating rata-rata sebagai angka manual pada Profile tanpa kebutuhan jelas karena edit/hapus review akan membuatnya mudah tidak sinkron.

## 9. Rencana pengujian dan bukti selesai

Review:

- Pembeli dan pengadopsi pada request selesai berhasil membuat review.
- Status pending/diterima/ditolak/dibatalkan ditolak.
- Barang selesai tanpa request selesai tidak memberi hak review.
- Penjual dan pengguna ketiga tidak dapat membuat review untuk request tersebut.
- Dua submit untuk request sama menghasilkan tepat satu review.
- Rating 0, 6, pecahan, kosong, dan teks ulasan tidak valid ditolak.
- Penulis dapat edit/hapus; orang lain ditolak meskipun mengirim POST langsung.
- Rating rata-rata dan count benar setelah create/update/delete; nol review tidak tampil sebagai 0/5.

Report:

- Target barang dan pengguna masing-masing dapat dilaporkan.
- Target kosong/ganda/tidak ada, pelaporan diri sendiri, dan duplikasi aktif ditolak.
- Orang lain, termasuk pihak terlapor, tidak dapat melihat isi laporan melalui halaman maupun JSON.
- Reporter dapat edit/hapus pending; in-review/closed terkunci.
- Pengguna biasa tidak dapat mengubah status atau mengisi identitas moderator lewat POST.
- Staff berizin dapat memproses laporan; staf tanpa izin model yang diperlukan ditolak.
- Soft-delete barang tidak merusak akses sah ke laporan/riwayat yang sudah ada.

Integrasi dan UI:

- Login/SSO, profil lengkap, csrf, method POST, HTMX partial dan redirect normal.
- Filter/pagination tidak menghilangkan kriteria aktif atau membocorkan laporan pengguna lain.
- Ulasan yang berisi HTML ditampilkan sebagai teks ter-escape, bukan dieksekusi.
- Tombol review muncul untuk pihak yang tepat setelah complete normal maupun bulk action dengan accepted request.
- Lebar ponsel dan desktop, form error, toast, dan navbar/footer diperiksa langsung.
- Test API eksternal memakai mock; jangan membebani Nominatim selama unit test.

Jalankan pengujian modul dahulu, lalu seluruh aplikasi pada branch gabungan. Catat hasil nyata dan coverage; jangan mengklaim lulus dari sekadar keberadaan berkas test. Periksa migrasi belum tersimpan, system check Django, dan deployment PWS dengan akun uji.

## 10. Jadwal pelaksanaan 27–30 Oktober 2026

| Waktu | Fokus | Kriteria selesai |
| --- | --- | --- |
| 27 Oktober | Kunci kontrak dengan Owen/Elvis, aturan CRUD/report, layout minimum, model dan migrasi | Model/relasi disepakati; hak review dan target report dapat diuji |
| 28 Oktober | Selesaikan layanan, form, CRUD, daftar/filter, otorisasi, admin | Semua P0 berfungsi dengan test aturan bisnis dan akses |
| 29 Oktober | HTMX/responsif, integrasi tombol katalog/profil, gabungkan dependensi | Demo end-to-end adopsi dan jual, serta report, berjalan di aplikasi gabungan |
| 30 Oktober pagi–sore | Regression, coverage, seed, deploy dan perbaikan | Semua test gabungan lulus, URL PWS/Figma/README lengkap, data utama cukup |
| 30 Oktober sebelum malam | Latihan demo dan pengumpulan lebih awal | Commit final tercatat dan tautan repo dikumpulkan sebelum 23.59 WIB |

Jika waktu menyempit, kurangi P1 terlebih dahulu. Pertahankan CRUD review, report privat, otorisasi server, test aturan inti, dan deployment.

## 11. Checklist koordinasi dan demo

Keputusan yang perlu disepakati sejak awal, sambil pekerjaan mandiri tetap berjalan:

- Owen: status final, entry point review, penggunaan bulk done, retensi item/request, dan basis branch integrasi.
- Elvis: letak rating, ulasan/laporan saya, kebutuhan profil publik, dan pendekatan Tailwind/token bersama.
- Kelompok: operator staff, kebijakan report pending, data demo, minimal 50 barang tersedia, dan siapa penanggung jawab deploy.
- Asdos: interpretasi filter Public API per anggota dan rubrik rinci yang belum ada dalam PDF.

Skenario demo 5–7 menit:

1. Akun A memasang barang, akun B mengajukan, A menerima lalu menyelesaikan serah terima.
2. B memberi rating/ulasan; tampil di daftar dan ringkasan pemilik.
3. B mengubah ulasan; agregat ikut berubah. B menghapus review; count menyesuaikan.
4. Akun C mencoba mengulas transaksi tersebut melalui URL langsung dan ditolak.
5. B melaporkan barang atau A, membaca laporan sendiri, lalu mengubah/hapus laporan pending.
6. Buat laporan lagi; staff berizin meninjaunya. Akun lain tidak dapat melihatnya dan reporter tidak bisa mengedit setelah diperiksa.
7. Tunjukkan filter HTMX dan tampilan ponsel, lalu bukti pengujian.

Artefak akhir: kode app dan migrasi, desain tambahan state CRUD/report, test dan laporan coverage, data demo yang bisa diulang tanpa menggandakan isi, PR dengan pembagian kontribusi, README terbaru, serta deployment teruji. Seed tidak boleh menghapus data pengguna yang sudah ada.

## 12. Sumber rujukan

- Dokumen tugas lokal: `C:/Users/ACER/Downloads/midterm.pdf`, halaman 1–4.
- Repository: https://github.com/pbp-b-kelompok-2/ui-kembali
- Kontrak transaksi: `origin/feat/owen-requests:katalog/services.py`, `katalog/models.py`, template request dan URL.
- Integrasi lokasi: `origin/feat/owen-osm:katalog/geocoding.py`, filter dan pengujian terkait.
- Integrasi profil: `origin/feat/vis:auth_ssoui/views.py`, URL, template profil dan base profil.
- Kerangka lokal: `templates/base.html`, `static/css/root.css`, `katalog/decorators.py`, template dasar katalog dan contoh test CRUD.
- Figma halaman review/report: https://www.figma.com/design/rTVD1SeON4Oi2QX6KCMLmN/UIKembali?node-id=20-11438
