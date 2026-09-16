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
| 1 | **Profile** | Menangani autentikasi pengguna yang terintegrasi dengan **SSO UI**, serta pengelolaan data profil pengguna seperti nama, fakultas, angkatan, foto profil, dan informasi lainnya. | **Padjri** |
| 2 | **Posting & Katalog Barang** | Menangani CRUD posting barang yang ingin diberikan atau dijual, termasuk nama, deskripsi, kategori, kondisi, foto, lokasi, jenis transaksi (adopsi/jual), dan harga. Modul ini juga menyediakan katalog, pencarian, filter, halaman detail barang, serta pengelolaan permintaan adopsi atau pembelian. | **Owen** |
| 3 | **Chat** | Menangani komunikasi antar pengguna, khususnya antara pemilik/penjual dengan calon pengadopsi/pembeli. Modul mencakup pembuatan percakapan, pengiriman pesan, dan pengelolaan pesan. | **Axel** |
| 4 | **Forum** | Menyediakan ruang diskusi bagi pengguna untuk berbagi informasi, pengalaman, tips, dan pertanyaan seputar barang bekas, kehidupan kost, serta penggunaan kembali barang. Modul mencakup CRUD posting forum dan interaksi pengguna pada forum. | **Dimas** |
| 5 | **Review & Report** | Menangani pemberian rating dan ulasan setelah proses adopsi atau pembelian selesai, serta pelaporan terhadap barang atau pengguna yang bermasalah. | **Elvis** |

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
[Masukkan tautan dokumentasi UI SSO]

---

## 🎨 Desain Figma

Desain antarmuka UIKembali dibuat menggunakan Figma.

**Figma:**  
[Masukkan tautan Figma di sini]

---

## 🚀 Deployment

Aplikasi UIKembali telah di-deploy menggunakan PWS.

**PWS:**  
[Masukkan tautan deployment PWS di sini]


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
