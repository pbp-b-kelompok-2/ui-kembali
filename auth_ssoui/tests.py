from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse
from PIL import Image

from .forms import ProfileForm
from .models import Profile

User = get_user_model()


# ─────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────

def make_user(username="testuser", password="testpass123"):
    """Buat user biasa yang bisa login dengan password."""
    user = User.objects.create_user(username=username, password=password)
    return user


def make_complete_profile(user):
    """Buat atau update profile user menjadi is_complete=True."""
    profile, _ = Profile.objects.get_or_create(user=user)
    profile.nama = "Test User"
    profile.peran = "Mahasiswa"
    profile.faculty = "Ilmu Komputer"
    profile.angkatan = "2023"
    profile.nama_panggilan = "Tester"
    profile.no_hp = "081234567890"
    profile.is_complete = True
    profile.save()
    return profile


def make_image_file(fmt="PNG", size=(100, 100), file_size_bytes=None):
    """
    Buat SimpleUploadedFile berisi gambar valid.
    Jika file_size_bytes diset, isi file ditambah padding agar ukurannya melebihi batas.
    """
    buf = BytesIO()
    img = Image.new("RGB", size, color="red")
    img.save(buf, format=fmt)
    content = buf.getvalue()
    if file_size_bytes and len(content) < file_size_bytes:
        content = content + b"\x00" * (file_size_bytes - len(content))
    ext = fmt.lower() if fmt != "JPEG" else "jpg"
    return SimpleUploadedFile(f"test.{ext}", content, content_type=f"image/{fmt.lower()}")


# ─────────────────────────────────────────────────────────────
#  1. Model Tests
# ─────────────────────────────────────────────────────────────

class ProfileModelTest(TestCase):
    """Uji semua aspek model Profile."""

    def setUp(self):
        self.user = make_user()
        self.profile = make_complete_profile(self.user)

    # --- __str__ ---
    def test_str_returns_nama_dan_username(self):
        """__str__ harus mengembalikan 'Nama (username)'."""
        self.assertEqual(str(self.profile), "Test User (testuser)")

    # --- inisial ---
    def test_inisial_dua_kata(self):
        """inisial() harus mengambil huruf pertama nama depan dan belakang."""
        self.profile.nama = "Budi Santoso"
        self.assertEqual(self.profile.inisial(), "BS")

    def test_inisial_satu_kata(self):
        """Jika nama hanya satu kata, huruf pertama dan terakhir adalah sama."""
        self.profile.nama = "Budi"
        self.assertEqual(self.profile.inisial(), "B")

    # --- OneToOne relation ---
    def test_profile_terhubung_ke_user(self):
        """Profile harus memiliki relasi OneToOne ke User."""
        self.assertEqual(self.user.profile, self.profile)

    # --- is_complete default ---
    def test_is_complete_default_false(self):
        """Profile baru harus memiliki is_complete=False secara default."""
        new_user = make_user(username="newuser")
        profile = Profile.objects.create(user=new_user)
        self.assertFalse(profile.is_complete)

    # --- field max_length ---
    def test_nama_panggilan_max_length(self):
        """nama_panggilan harus memiliki max_length=50."""
        field = Profile._meta.get_field("nama_panggilan")
        self.assertEqual(field.max_length, 50)

    def test_bio_max_length(self):
        """bio harus memiliki max_length=160."""
        field = Profile._meta.get_field("bio")
        self.assertEqual(field.max_length, 160)

    # --- validator no_hp ---
    def test_no_hp_valid(self):
        """no_hp dengan format benar harus lolos validator."""
        from django.core.exceptions import ValidationError
        self.profile.no_hp = "081234567890"
        try:
            self.profile.full_clean()
        except ValidationError as e:
            self.assertNotIn("no_hp", e.message_dict)

    def test_no_hp_invalid(self):
        """no_hp dengan format salah harus gagal validasi."""
        from django.core.exceptions import ValidationError
        self.profile.no_hp = "12345"
        with self.assertRaises(ValidationError):
            self.profile.full_clean()

    # --- validator angkatan ---
    def test_angkatan_valid(self):
        """angkatan 4 digit diawali 20 harus lolos validator."""
        from django.core.exceptions import ValidationError
        self.profile.angkatan = "2025"
        try:
            self.profile.full_clean()
        except ValidationError as e:
            self.assertNotIn("angkatan", e.message_dict)

    def test_angkatan_invalid(self):
        """angkatan yang tidak diawali '20' harus gagal validasi."""
        from django.core.exceptions import ValidationError
        self.profile.angkatan = "1999"
        with self.assertRaises(ValidationError):
            self.profile.full_clean()

    def test_angkatan_terlalu_pendek(self):
        """angkatan kurang dari 4 digit harus gagal validasi."""
        from django.core.exceptions import ValidationError
        self.profile.angkatan = "202"
        with self.assertRaises(ValidationError):
            self.profile.full_clean()


# ─────────────────────────────────────────────────────────────
#  2. Form Tests
# ─────────────────────────────────────────────────────────────

class ProfileFormTest(TestCase):
    """Uji ProfileForm: field, disabled field, required, validasi pfp."""

    def setUp(self):
        self.user = make_user()
        self.profile = make_complete_profile(self.user)
        self.valid_data = {
            "nama_panggilan": "Jojo",
            "no_hp": "081234567890",
            "titik_favorit": "Perpustakaan UI",
            "bio": "Halo dunia!",
        }

    # --- Field filtering ---
    def test_form_hanya_tampilkan_field_yang_diminta(self):
        """Form dengan parameter fields hanya boleh berisi field yang diminta."""
        fields = ["nama_panggilan", "no_hp"]
        form = ProfileForm(fields=fields)
        self.assertSetEqual(set(form.fields.keys()), set(fields))

    def test_form_tanpa_fields_argument_berisi_semua_field(self):
        """Form tanpa parameter fields harus berisi semua field yang didefinisikan."""
        from .forms import SSO_FIELDS, USER_FIELDS
        form = ProfileForm()
        expected = set(SSO_FIELDS + USER_FIELDS)
        self.assertEqual(set(form.fields.keys()), expected)

    # --- Disabled fields ---
    def test_field_sso_disabled_saat_ada_di_fields(self):
        """Field SSO (nama, faculty, angkatan) harus disabled jika disertakan di fields."""
        form = ProfileForm(fields=["nama", "faculty", "angkatan", "nama_panggilan", "no_hp"])
        self.assertTrue(form.fields["nama"].disabled)
        self.assertTrue(form.fields["faculty"].disabled)
        self.assertTrue(form.fields["angkatan"].disabled)

    def test_field_sso_disabled_saat_fields_none(self):
        """Field SSO harus disabled jika parameter fields tidak diberikan."""
        form = ProfileForm()
        self.assertTrue(form.fields["nama"].disabled)
        self.assertTrue(form.fields["faculty"].disabled)

    # --- Required fields ---
    def test_nama_panggilan_required(self):
        """nama_panggilan harus required saat ada di fields."""
        form = ProfileForm(fields=["nama_panggilan", "no_hp"])
        self.assertTrue(form.fields["nama_panggilan"].required)

    def test_no_hp_required(self):
        """no_hp harus required saat ada di fields."""
        form = ProfileForm(fields=["nama_panggilan", "no_hp"])
        self.assertTrue(form.fields["no_hp"].required)

    # --- Form valid ---
    def test_form_valid_dengan_data_lengkap(self):
        """Form harus valid jika semua field wajib diisi dengan benar."""
        form = ProfileForm(
            data=self.valid_data,
            fields=["nama_panggilan", "no_hp", "titik_favorit", "bio"],
            instance=self.profile,
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_form_invalid_tanpa_nama_panggilan(self):
        """Form harus invalid jika nama_panggilan kosong padahal required."""
        data = dict(self.valid_data, nama_panggilan="")
        form = ProfileForm(
            data=data,
            fields=["nama_panggilan", "no_hp"],
            instance=self.profile,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("nama_panggilan", form.errors)

    def test_form_invalid_no_hp_salah_format(self):
        """Form harus invalid jika no_hp tidak sesuai format."""
        data = dict(self.valid_data, no_hp="12345")
        form = ProfileForm(
            data=data,
            fields=["nama_panggilan", "no_hp"],
            instance=self.profile,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("no_hp", form.errors)

    # --- clean_pfp: ukuran file ---
    def test_clean_pfp_tolak_file_terlalu_besar(self):
        """clean_pfp harus menolak file yang melebihi 2 MB."""
        big_file = make_image_file(fmt="PNG", file_size_bytes=3 * 1024 * 1024)
        form = ProfileForm(
            data=self.valid_data,
            files={"pfp": big_file},
            fields=["nama_panggilan", "no_hp", "pfp"],
            instance=self.profile,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("pfp", form.errors)
        self.assertIn("2 MB", form.errors["pfp"][0])

    # --- clean_pfp: format ---
    def test_clean_pfp_tolak_format_tidak_didukung(self):
        """clean_pfp harus menolak format GIF."""
        buf = BytesIO()
        Image.new("P", (10, 10)).save(buf, format="GIF")
        gif_file = SimpleUploadedFile("test.gif", buf.getvalue(), content_type="image/gif")
        form = ProfileForm(
            data=self.valid_data,
            files={"pfp": gif_file},
            fields=["nama_panggilan", "no_hp", "pfp"],
            instance=self.profile,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("pfp", form.errors)

    def test_clean_pfp_terima_png_valid(self):
        """clean_pfp harus menerima file PNG yang ukurannya wajar."""
        png_file = make_image_file(fmt="PNG")
        form = ProfileForm(
            data=self.valid_data,
            files={"pfp": png_file},
            fields=["nama_panggilan", "no_hp", "pfp"],
            instance=self.profile,
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_clean_pfp_terima_jpeg_valid(self):
        """clean_pfp harus menerima file JPEG yang ukurannya wajar."""
        jpeg_file = make_image_file(fmt="JPEG")
        form = ProfileForm(
            data=self.valid_data,
            files={"pfp": jpeg_file},
            fields=["nama_panggilan", "no_hp", "pfp"],
            instance=self.profile,
        )
        self.assertTrue(form.is_valid(), form.errors)


# ─────────────────────────────────────────────────────────────
#  3. Decorator Tests
# ─────────────────────────────────────────────────────────────

class ProfileRequiredDecoratorTest(TestCase):
    """Uji decorator @profile_required."""

    def setUp(self):
        self.client = Client()
        self.url = reverse("auth_ssoui:profile")

    def test_redirect_ke_login_jika_belum_login(self):
        """User yang belum login harus diredirect ke halaman login."""
        response = self.client.get(self.url)
        self.assertIn(response.status_code, [301, 302])
        self.assertIn("/auth/login/", response["Location"])

    def test_redirect_ke_lengkapi_profil_jika_belum_complete(self):
        """User yang login tapi belum lengkapi profil harus diredirect ke lengkapi_profil."""
        user = make_user(username="incomplete")
        Profile.objects.get_or_create(user=user)  # is_complete=False by default
        self.client.force_login(user)
        response = self.client.get(self.url)
        self.assertRedirects(
            response,
            reverse("auth_ssoui:lengkapi_profil"),
            fetch_redirect_response=False,
        )

    def test_akses_diterima_jika_profil_complete(self):
        """User dengan profil complete harus bisa mengakses halaman profil."""
        user = make_user(username="complete")
        make_complete_profile(user)
        self.client.force_login(user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)


# ─────────────────────────────────────────────────────────────
#  4. View Tests — lengkapi_profil
# ─────────────────────────────────────────────────────────────

class LengkapiProfilViewTest(TestCase):
    """Uji view lengkapi_profil (GET, POST valid, POST invalid, HTMX)."""

    def setUp(self):
        self.client = Client()
        self.url = reverse("auth_ssoui:lengkapi_profil")
        self.user = make_user(username="newbie")
        self.profile, _ = Profile.objects.get_or_create(user=self.user)
        self.profile.nama = "Budi Doremi"
        self.profile.faculty = "FMIPA"
        self.profile.angkatan = "2024"
        self.profile.save()

    def test_get_tampilkan_form(self):
        """GET harus mengembalikan status 200 dan menampilkan form."""
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context)

    def test_redirect_ke_login_jika_belum_login(self):
        """GET tanpa login harus redirect ke halaman login."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/auth/login/", response["Location"])

    def test_redirect_ke_profile_jika_sudah_complete(self):
        """Jika profil sudah complete, GET harus redirect ke profile page."""
        self.profile.is_complete = True
        self.profile.nama_panggilan = "Budi"
        self.profile.no_hp = "081234567890"
        self.profile.save()
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertRedirects(
            response,
            reverse("auth_ssoui:profile"),
            fetch_redirect_response=False,
        )

    def test_post_valid_set_is_complete_true(self):
        """POST dengan data valid harus menyimpan profil dan set is_complete=True."""
        self.client.force_login(self.user)
        data = {
            "nama_panggilan": "Budi",
            "no_hp": "081234567890",
            "titik_favorit": "Perpustakaan UI",
            "bio": "Halo!",
        }
        self.client.post(self.url, data)
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.is_complete)
        self.assertEqual(self.profile.peran, "Mahasiswa")

    def test_post_valid_redirect_ke_lobby(self):
        """POST valid tanpa HTMX harus redirect ke main:lobby."""
        self.client.force_login(self.user)
        data = {
            "nama_panggilan": "Budi",
            "no_hp": "081234567890",
        }
        response = self.client.post(self.url, data)
        self.assertRedirects(
            response,
            reverse("main:lobby"),
            fetch_redirect_response=False,
        )

    def test_post_invalid_render_form_dengan_error(self):
        """POST dengan data tidak valid harus re-render form dengan error."""
        self.client.force_login(self.user)
        data = {"nama_panggilan": "", "no_hp": "12345"}
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 200)

    def test_post_invalid_ada_header_hx_trigger_toast(self):
        """POST invalid harus mengandung header HX-Trigger berisi toast error."""
        self.client.force_login(self.user)
        data = {"nama_panggilan": "", "no_hp": "12345"}
        response = self.client.post(self.url, data)
        self.assertIn("HX-Trigger", response)
        import json
        trigger = json.loads(response["HX-Trigger"])
        self.assertEqual(trigger["toast"]["level"], "error")

    def test_post_valid_htmx_kembalikan_204(self):
        """POST valid via HTMX harus mengembalikan status 204."""
        self.client.force_login(self.user)
        data = {
            "nama_panggilan": "Budi",
            "no_hp": "081234567890",
        }
        response = self.client.post(
            self.url, data, HTTP_HX_REQUEST="true"
        )
        self.assertEqual(response.status_code, 204)

    def test_post_valid_htmx_ada_header_hx_trigger(self):
        """POST valid via HTMX harus mengandung header HX-Trigger dengan toast success."""
        self.client.force_login(self.user)
        data = {
            "nama_panggilan": "Budi",
            "no_hp": "081234567890",
        }
        response = self.client.post(
            self.url, data, HTTP_HX_REQUEST="true"
        )
        self.assertIn("HX-Trigger", response)
        import json
        trigger = json.loads(response["HX-Trigger"])
        self.assertEqual(trigger["toast"]["level"], "success")


# ─────────────────────────────────────────────────────────────
#  5. View Tests — edit_profil
# ─────────────────────────────────────────────────────────────

class EditProfilViewTest(TestCase):
    """Uji view edit_profil (GET, POST valid, POST invalid, HTMX)."""

    def setUp(self):
        self.client = Client()
        self.url = reverse("auth_ssoui:edit_profil")
        self.user = make_user(username="editor")
        self.profile = make_complete_profile(self.user)

    def test_get_kembalikan_200(self):
        """GET harus mengembalikan status 200."""
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_post_valid_simpan_perubahan(self):
        """POST valid harus menyimpan perubahan ke database."""
        self.client.force_login(self.user)
        data = {
            "nama_panggilan": "Editor Baru",
            "no_hp": "081234567890",
            "titik_favorit": "Kantin FT",
            "bio": "Bio baru",
        }
        self.client.post(self.url, data)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.nama_panggilan, "Editor Baru")

    def test_post_valid_redirect_ke_profile(self):
        """POST valid tanpa HTMX harus redirect ke halaman profil."""
        self.client.force_login(self.user)
        data = {
            "nama_panggilan": "Editor",
            "no_hp": "081234567890",
        }
        response = self.client.post(self.url, data)
        self.assertRedirects(
            response,
            reverse("auth_ssoui:profile"),
            fetch_redirect_response=False,
        )

    def test_post_invalid_ada_toast_error(self):
        """POST invalid harus mengembalikan HX-Trigger toast error."""
        self.client.force_login(self.user)
        data = {"no_hp": "BUKAN_NOMOR"}
        response = self.client.post(self.url, data)
        self.assertIn("HX-Trigger", response)
        import json
        trigger = json.loads(response["HX-Trigger"])
        self.assertEqual(trigger["toast"]["level"], "error")

    def test_post_valid_htmx_kembalikan_200_dan_toast_success(self):
        """POST valid via HTMX harus mengembalikan 200 dan toast success."""
        self.client.force_login(self.user)
        data = {
            "nama_panggilan": "HTMX Editor",
            "no_hp": "081234567890",
        }
        response = self.client.post(
            self.url, data, HTTP_HX_REQUEST="true"
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("HX-Trigger", response)
        import json
        trigger = json.loads(response["HX-Trigger"])
        self.assertEqual(trigger["toast"]["level"], "success")

    def test_redirect_ke_lengkapi_profil_jika_belum_complete(self):
        """User yang belum complete profil harus diredirect ke lengkapi_profil."""
        user = make_user(username="notcomplete")
        Profile.objects.get_or_create(user=user)
        self.client.force_login(user)
        response = self.client.get(self.url)
        self.assertRedirects(
            response,
            reverse("auth_ssoui:lengkapi_profil"),
            fetch_redirect_response=False,
        )


# ─────────────────────────────────────────────────────────────
#  6. View Tests — profile_page
# ─────────────────────────────────────────────────────────────

class ProfilePageViewTest(TestCase):
    """Uji view profile_page."""

    def setUp(self):
        self.client = Client()
        self.url = reverse("auth_ssoui:profile")
        self.user = make_user(username="viewer")
        self.profile = make_complete_profile(self.user)

    def test_halaman_profil_kembalikan_200(self):
        """Halaman profil harus mengembalikan status 200 untuk user yang valid."""
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_context_berisi_profile(self):
        """Context harus mengandung objek 'profile'."""
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertIn("profile", response.context)
        self.assertEqual(response.context["profile"], self.profile)

    def test_context_berisi_form(self):
        """Context harus mengandung 'form'."""
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertIn("form", response.context)

    def test_context_berisi_form_action(self):
        """Context harus mengandung 'form_action' yang mengarah ke edit_profil."""
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertIn("form_action", response.context)
        self.assertEqual(
            response.context["form_action"], reverse("auth_ssoui:edit_profil")
        )

    def test_redirect_jika_belum_login(self):
        """User yang belum login harus diredirect."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)


# ─────────────────────────────────────────────────────────────
#  7. URL Routing Tests
# ─────────────────────────────────────────────────────────────

class URLRoutingTest(TestCase):
    """Uji bahwa semua URL terdaftar dan dapat di-resolve."""

    def test_url_login(self):
        """URL auth/login/ harus bisa di-resolve."""
        url = reverse("auth_ssoui:login")
        self.assertEqual(url, "/auth/login/")

    def test_url_logout(self):
        """URL auth/logout/ harus bisa di-resolve."""
        url = reverse("auth_ssoui:logout")
        self.assertEqual(url, "/auth/logout/")

    def test_url_profile(self):
        """URL auth/profile/ harus bisa di-resolve."""
        url = reverse("auth_ssoui:profile")
        self.assertEqual(url, "/auth/profile/")

    def test_url_lengkapi_profil(self):
        """URL auth/profile/fill/ harus bisa di-resolve."""
        url = reverse("auth_ssoui:lengkapi_profil")
        self.assertEqual(url, "/auth/profile/fill/")

    def test_url_edit_profil(self):
        """URL auth/profile/edit/ harus bisa di-resolve."""
        url = reverse("auth_ssoui:edit_profil")
        self.assertEqual(url, "/auth/profile/edit/")


# ─────────────────────────────────────────────────────────────
#  8. with_toast Helper Tests
# ─────────────────────────────────────────────────────────────

class WithToastHelperTest(TestCase):
    """Uji fungsi helper with_toast."""

    def test_with_toast_menambahkan_header_hx_trigger(self):
        """with_toast harus menambahkan header HX-Trigger ke response."""
        from django.http import HttpResponse
        import json
        from .views import with_toast

        response = HttpResponse("ok")
        result = with_toast(response, "Pesan sukses", "success")
        self.assertIn("HX-Trigger", result)
        data = json.loads(result["HX-Trigger"])
        self.assertEqual(data["toast"]["msg"], "Pesan sukses")
        self.assertEqual(data["toast"]["level"], "success")

    def test_with_toast_level_error(self):
        """with_toast harus bisa mengeset level error."""
        from django.http import HttpResponse
        import json
        from .views import with_toast

        response = HttpResponse("bad")
        result = with_toast(response, "Ada masalah", "error")
        data = json.loads(result["HX-Trigger"])
        self.assertEqual(data["toast"]["level"], "error")
