from datetime import timedelta

from django.test import SimpleTestCase
from django.utils import timezone

from katalog.templatetags.katalog_extras import rupiah, waktu_lalu


class RupiahFilterTests(SimpleTestCase):
    def test_uses_dots_as_thousand_separators(self):
        self.assertEqual(rupiah(55000), "Rp55.000")
        self.assertEqual(rupiah(1_250_000), "Rp1.250.000")
        self.assertEqual(rupiah(900), "Rp900")

    def test_empty_price_is_free(self):
        self.assertEqual(rupiah(None), "Gratis")


class WaktuLaluFilterTests(SimpleTestCase):
    def ago(self, **delta):
        return waktu_lalu(timezone.now() - timedelta(**delta))

    def test_buckets(self):
        self.assertEqual(self.ago(seconds=20), "baru saja")
        self.assertEqual(self.ago(minutes=5), "5 menit lalu")
        self.assertEqual(self.ago(hours=2), "2 jam lalu")
        self.assertEqual(self.ago(days=1, hours=3), "kemarin")
        self.assertEqual(self.ago(days=3), "3 hari lalu")
        self.assertEqual(self.ago(days=70), "2 bulan lalu")
        self.assertEqual(self.ago(days=800), "2 tahun lalu")
