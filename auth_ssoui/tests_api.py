from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Profile


User = get_user_model()


class ProfileAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="api-user", password="test-pass")
        self.other_user = User.objects.create_user(
            username="other-user", password="test-pass",
        )
        self.profile = Profile.objects.create(
            user=self.user,
            nama="Nama dari SSO",
            peran="Mahasiswa",
            faculty="Fakultas SSO",
            angkatan="2023",
        )
        self.other_profile = Profile.objects.create(
            user=self.other_user,
            nama="Pengguna Lain",
            faculty="Fakultas Lain",
            angkatan="2022",
            is_complete=True,
        )
        self.detail_url = reverse("auth_api:profile-detail")
        self.edit_url = reverse("auth_api:profile-edit")
        self.complete_url = reverse("auth_api:profile-complete")

    def test_semua_endpoint_menolak_pengguna_anonymous(self):
        for url, method, data in (
            (self.detail_url, "get", None),
            (self.edit_url, "patch", {"bio": "Bio baru"}),
            (
                self.complete_url,
                "patch",
                {"nama_panggilan": "Api", "no_hp": "081234567890"},
            ),
        ):
            with self.subTest(url=url):
                if method == "get":
                    response = self.client.get(url)
                else:
                    response = self.client.patch(url, data, format="json")
                self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_detail_mengembalikan_profil_pengguna_yang_login(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get(self.detail_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["username"], self.user.username)
        self.assertEqual(response.data["nama"], "Nama dari SSO")
        self.assertFalse(response.data["is_complete"])
        self.assertNotEqual(response.data["username"], self.other_user.username)

    def test_detail_membuat_profil_jika_belum_ada(self):
        user_without_profile = User.objects.create_user(
            username="new-api-user", password="test-pass",
        )
        self.client.force_authenticate(user=user_without_profile)

        response = self.client.get(self.detail_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(Profile.objects.filter(user=user_without_profile).exists())
        self.assertEqual(response.data["username"], user_without_profile.username)

    def test_pengguna_belum_lengkap_dapat_melengkapi_profil(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.patch(
            self.complete_url,
            {
                "nama_panggilan": "Api",
                "no_hp": "081234567890",
                "titik_favorit": "Perpustakaan UI",
                "nama": "Nama kiriman klien",
                "faculty": "Fakultas kiriman klien",
                "angkatan": "2099",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.is_complete)
        self.assertEqual(self.profile.nama_panggilan, "Api")
        self.assertEqual(self.profile.nama, "Nama dari SSO")
        self.assertEqual(self.profile.faculty, "Fakultas SSO")
        self.assertEqual(self.profile.angkatan, "2023")

    def test_pelengkapan_profil_menolak_field_wajib_yang_kosong(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.patch(
            self.complete_url,
            {"nama_panggilan": "Api", "no_hp": ""},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("no_hp", response.data)
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.is_complete)

    def test_pengguna_dengan_profil_lengkap_tidak_dapat_melengkapi_lagi(self):
        self.client.force_authenticate(user=self.other_user)

        response = self.client.patch(
            self.complete_url,
            {"nama_panggilan": "Lain", "no_hp": "081234567890"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["detail"], "Profil sudah lengkap.")

    def test_pengguna_belum_lengkap_tidak_dapat_mengedit_profil(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.patch(
            self.edit_url,
            {"bio": "Bio baru"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["detail"], "Lengkapi profil terlebih dahulu.")

    def test_pengguna_dapat_mengedit_field_profil_yang_diizinkan(self):
        self.profile.is_complete = True
        self.profile.nama_panggilan = "Lama"
        self.profile.no_hp = "081234567890"
        self.profile.save()
        self.client.force_authenticate(user=self.user)

        response = self.client.patch(
            self.edit_url,
            {
                "nama_panggilan": "Baru",
                "bio": "Bio baru",
                "nama": "Nama kiriman klien",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.nama_panggilan, "Baru")
        self.assertEqual(self.profile.bio, "Bio baru")
        self.assertEqual(self.profile.nama, "Nama dari SSO")

    def test_edit_profil_memvalidasi_nomor_hp(self):
        self.profile.is_complete = True
        self.profile.save()
        self.client.force_authenticate(user=self.user)

        response = self.client.patch(
            self.edit_url,
            {"no_hp": "nomor-tidak-valid"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("no_hp", response.data)


