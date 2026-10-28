"""python manage.py seed_katalog

Fills the catalog with 50+ realistic items from 5 demo users. Safe to run
again: existing users and items (same owner + name) are skipped.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from katalog.geocoding import lookup_place
from katalog.models import Item

User = get_user_model()

USERS = ["demo_rina", "demo_budi", "demo_sari", "demo_yoga", "demo_nadia"]

C = Item.Category
K = Item.Condition
# (name, category, condition, price or None for free, meeting place, description)
ITEMS = [
    ("Buku Kalkulus Purcell Edisi 9", C.BUKU, K.BAIK, 60000, "Perpustakaan UI", "Ada sedikit stabilo di bab 2, halaman lengkap."),
    ("Buku Pengantar Ekonomi Mankiw", C.BUKU, K.CUKUP_BAIK, None, "Kukusan", "Sampul agak lecek, isi masih bersih."),
    ("Buku Struktur Data dan Algoritma", C.BUKU, K.SEPERTI_BARU, 85000, "Fasilkom UI", "Baru dipakai satu semester, tanpa coretan."),
    ("Novel Laskar Pelangi", C.BUKU, K.LAYAK_PAKAI, None, "Pondok Cina", "Kertas menguning, cocok untuk bacaan santai."),
    ("Buku Fisika Dasar Halliday", C.BUKU, K.BAIK, 70000, "Perpustakaan UI", "Jilid 1, ada catatan pensil kecil."),
    ("Modul Basis Data", C.BUKU, K.CUKUP_BAIK, None, "Fasilkom UI", "Fotokopi modul lengkap dengan latihan soal."),
    ("Kamus Inggris-Indonesia Echols", C.BUKU, K.BAIK, 40000, "Margonda", "Edisi lengkap, sampul keras."),
    ("Buku Statistika Walpole", C.BUKU, K.LAYAK_PAKAI, 25000, "Beji", "Beberapa halaman terlipat, isi terbaca."),
    ("Meja belajar lipat", C.PERABOT, K.BAIK, 75000, "Kukusan", "Kayu, bisa dilipat, cocok untuk kamar kos."),
    ("Kursi plastik", C.PERABOT, K.CUKUP_BAIK, None, "Pondok Cina", "Dua buah, warna biru, masih kokoh."),
    ("Rak buku 3 susun", C.PERABOT, K.BAIK, 90000, "Beji", "Bahan MDF, mudah dibongkar pasang."),
    ("Kasur busa single", C.PERABOT, K.LAYAK_PAKAI, None, "Kukusan", "Tebal 10 cm, sudah dijemur, tanpa noda."),
    ("Lemari plastik 4 laci", C.PERABOT, K.CUKUP_BAIK, 50000, "Margonda", "Satu laci agak seret, lainnya lancar."),
    ("Gantungan baju berdiri", C.PERABOT, K.BAIK, None, "Asrama UI", "Besi, tinggi 160 cm, sekrup lengkap."),
    ("Cermin dinding", C.PERABOT, K.SEPERTI_BARU, 45000, "Pondok Cina", "Ukuran 40x60 cm, bingkai kayu."),
    ("Karpet lantai kamar", C.PERABOT, K.CUKUP_BAIK, None, "Asrama UI", "Ukuran 2x1,5 m, sudah dicuci."),
    ("Kipas angin meja", C.ELEKTRONIK, K.BAIK, 80000, "Kukusan", "Tiga kecepatan, putaran masih normal."),
    ("Rice cooker mini", C.ELEKTRONIK, K.CUKUP_BAIK, 70000, "Pondok Cina", "Kapasitas 0,6 L, pas untuk satu orang."),
    ("Lampu belajar LED", C.ELEKTRONIK, K.SEPERTI_BARU, 55000, "Fasilkom UI", "Cahaya bisa diatur, kabel USB."),
    ("Kalkulator scientific Casio", C.ELEKTRONIK, K.BAIK, 120000, "Fasilkom UI", "fx-991ID, baterai baru diganti."),
    ("Mouse wireless", C.ELEKTRONIK, K.BAIK, 60000, "Stasiun UI", "Receiver lengkap, klik masih empuk."),
    ("Keyboard mekanikal", C.ELEKTRONIK, K.SEPERTI_BARU, 350000, "Fasilkom UI", "Switch merah, jarang dipakai."),
    ("Setrika listrik", C.ELEKTRONIK, K.LAYAK_PAKAI, None, "Beji", "Panas normal, gagang sedikit retak."),
    ("Stop kontak 4 lubang", C.ELEKTRONIK, K.BAIK, None, "Kukusan", "Kabel 3 meter, ada saklar."),
    ("Headphone kabel", C.ELEKTRONIK, K.CUKUP_BAIK, 75000, "Margonda", "Suara jernih, busa telinga agak mengelupas."),
    ("Jaket almamater UI ukuran M", C.PAKAIAN, K.BAIK, 100000, "Asrama UI", "Warna masih cerah, resleting lancar."),
    ("Kemeja putih formal", C.PAKAIAN, K.SEPERTI_BARU, 50000, "Margonda", "Ukuran L, dipakai sekali untuk sidang."),
    ("Jas hujan ponco", C.PAKAIAN, K.CUKUP_BAIK, None, "Stasiun UI", "Tidak bocor, ada kantong penyimpan."),
    ("Sepatu olahraga ukuran 42", C.PAKAIAN, K.LAYAK_PAKAI, 60000, "Pondok Cina", "Sol masih tebal, sudah dicuci."),
    ("Kaos panitia acara kampus", C.PAKAIAN, K.BAIK, None, "Fasilkom UI", "Ukuran M dan L, masing-masing dua."),
    ("Celana bahan hitam", C.PAKAIAN, K.BAIK, 45000, "Kukusan", "Ukuran 30, cocok untuk magang."),
    ("Tas ransel laptop", C.PAKAIAN, K.CUKUP_BAIK, 80000, "Beji", "Muat laptop 15 inci, resleting lengkap."),
    ("Topi rimba", C.PAKAIAN, K.SEPERTI_BARU, None, "Asrama UI", "Bekas kegiatan pecinta alam, masih baru."),
    ("Set pulpen gel 10 warna", C.ALAT_TULIS, K.SEPERTI_BARU, 30000, "Fasilkom UI", "Baru dibuka, tinta penuh."),
    ("Binder A5 dan kertas", C.ALAT_TULIS, K.BAIK, None, "Perpustakaan UI", "Binder plus sisa kertas sekitar 50 lembar."),
    ("Penggaris dan jangka", C.ALAT_TULIS, K.CUKUP_BAIK, None, "Kukusan", "Set gambar teknik, jangka masih kencang."),
    ("Papan tulis kecil", C.ALAT_TULIS, K.BAIK, 35000, "Pondok Cina", "Ukuran 40x60, bonus spidol."),
    ("Highlighter 5 warna", C.ALAT_TULIS, K.LAYAK_PAKAI, None, "Beji", "Tinta tinggal setengah."),
    ("Kertas HVS A4 satu rim", C.ALAT_TULIS, K.SEPERTI_BARU, 40000, "Margonda", "Belum dibuka, 70 gram."),
    ("Stapler dan isinya", C.ALAT_TULIS, K.BAIK, None, "Fasilkom UI", "Stapler besar plus dua kotak isi."),
    ("Panci kecil", C.DAPUR, K.CUKUP_BAIK, None, "Kukusan", "Diameter 16 cm, ada tutupnya."),
    ("Teflon 20 cm", C.DAPUR, K.BAIK, 50000, "Pondok Cina", "Lapisan anti lengket masih bagus."),
    ("Set piring dan gelas", C.DAPUR, K.BAIK, None, "Asrama UI", "Empat piring dan empat gelas."),
    ("Dispenser galon", C.DAPUR, K.LAYAK_PAKAI, 60000, "Beji", "Hanya air normal, pemanas mati."),
    ("Termos air 1 liter", C.DAPUR, K.SEPERTI_BARU, 45000, "Margonda", "Tahan panas sampai 12 jam."),
    ("Kotak makan bersekat", C.DAPUR, K.BAIK, None, "Fasilkom UI", "Dua buah, tutup rapat."),
    ("Payung lipat", C.LAINNYA, K.CUKUP_BAIK, None, "Stasiun UI", "Rangka utuh, kain sedikit pudar."),
    ("Raket badminton", C.LAINNYA, K.BAIK, 90000, "Asrama UI", "Senar baru diganti, bonus kok."),
    ("Matras yoga", C.LAINNYA, K.SEPERTI_BARU, 70000, "Kukusan", "Tebal 6 mm, ada tas."),
    ("Gitar akustik", C.LAINNYA, K.LAYAK_PAKAI, 250000, "Pondok Cina", "Senar perlu diganti, badan aman."),
    ("Helm half face", C.LAINNYA, K.BAIK, 120000, "Margonda", "Ukuran L, kaca bening tanpa baret."),
    ("Botol minum 1 liter", C.LAINNYA, K.SEPERTI_BARU, None, "Perpustakaan UI", "Hadiah seminar, belum dipakai."),
]


class Command(BaseCommand):
    help = "Isi katalog dengan 50+ barang contoh dari 5 pengguna demo."

    def handle(self, *args, **options):
        owners = []
        for username in USERS:
            user, created = User.objects.get_or_create(username=username)
            if created:
                user.set_unusable_password()  # demo accounts can't log in
                user.save()
            owners.append(user)

        created_count = 0
        for i, (name, category, condition, price, place, description) in enumerate(ITEMS):
            owner = owners[i % len(owners)]
            if Item.all_objects.filter(owner=owner, name=name).exists():
                continue
            # All seed places are in the campus table, so no API call is needed.
            spot = lookup_place(place)
            Item.objects.create(
                owner=owner,
                name=name,
                description=description,
                category=category,
                condition=condition,
                location_name=place,
                latitude=spot.lat,
                longitude=spot.lng,
                transaction_type=Item.TransactionType.JUAL if price else Item.TransactionType.ADOPSI,
                price=price,
                contact=f"Line: {owner.username}",
            )
            created_count += 1

        self.stdout.write(self.style.SUCCESS(f"{created_count} barang baru dibuat."))
