import shutil
import tempfile
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from katalog.forms import ItemForm
from katalog.models import MAX_PHOTO_SIDE, Item

from .test_forms import form_data
from .test_models import make_item
from .test_views_crud import HX, VALID_POST

User = get_user_model()
MEDIA_ROOT = tempfile.mkdtemp()


def image_file(fmt="PNG", size=(100, 100), name="foto.png", exif=None):
    buffer = BytesIO()
    extra = {"exif": exif} if exif else {}
    Image.new("RGB", size, color="red").save(buffer, format=fmt, **extra)
    return SimpleUploadedFile(name, buffer.getvalue(), content_type=f"image/{fmt.lower()}")


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class PhotoTestCase(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        cache.clear()  # rate-limit counters live in the cache
        self.owner = User.objects.create_user("pemilik", password="pw")


class ItemPhotoModelTests(PhotoTestCase):
    def test_photo_url_is_empty_without_a_photo(self):
        self.assertEqual(make_item(self.owner).photo_url, "")

    def test_upload_is_saved_as_webp_under_katalog(self):
        item = make_item(self.owner, photo=image_file())
        self.assertRegex(item.photo.name, r"^katalog/[0-9a-f]{32}\.webp$")
        self.assertEqual(item.photo_url, item.photo.url)
        with Image.open(item.photo.path) as saved:
            self.assertEqual(saved.format, "WEBP")

    def test_big_photo_is_shrunk(self):
        item = make_item(self.owner, photo=image_file(size=(3000, 1500)))
        with Image.open(item.photo.path) as saved:
            self.assertEqual(saved.size, (MAX_PHOTO_SIDE, MAX_PHOTO_SIDE // 2))

    def test_exif_metadata_is_removed(self):
        exif = Image.Exif()
        exif[0x010F] = "Kamera Owen"
        item = make_item(self.owner, photo=image_file(fmt="JPEG", name="a.jpg", exif=exif))
        with Image.open(item.photo.path) as saved:
            self.assertEqual(len(saved.getexif()), 0)

    def test_replaced_photo_file_is_deleted(self):
        item = make_item(self.owner, photo=image_file())
        old_name = item.photo.name
        storage = item.photo.storage
        item.photo = image_file()
        with self.captureOnCommitCallbacks(execute=True):
            item.save()
        self.assertNotEqual(item.photo.name, old_name)
        self.assertFalse(storage.exists(old_name))

    def test_soft_delete_and_restore_keep_the_photo(self):
        item = make_item(self.owner, photo=image_file())
        storage = item.photo.storage
        with self.captureOnCommitCallbacks(execute=True):
            item.soft_delete()
            item.restore()
        self.assertTrue(storage.exists(item.photo.name))


class ItemPhotoFormTests(PhotoTestCase):
    def form_with(self, photo):
        return ItemForm(data=form_data(), files={"photo": photo})

    def test_url_field_is_gone(self):
        self.assertNotIn("photo_url", ItemForm.base_fields)
        self.assertIn("photo", ItemForm.base_fields)

    def test_photo_is_optional(self):
        self.assertTrue(ItemForm(data=form_data()).is_valid())

    def test_accepts_jpg_png_webp(self):
        for fmt in ("JPEG", "PNG", "WEBP"):
            form = self.form_with(image_file(fmt=fmt, name=f"a.{fmt.lower()}"))
            self.assertTrue(form.is_valid(), form.errors)

    def test_rejects_a_file_that_is_not_an_image(self):
        form = self.form_with(SimpleUploadedFile("a.png", b"bukan gambar"))
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors["photo"], ["Berkas harus berupa gambar."])

    def test_rejects_other_image_formats(self):
        form = self.form_with(image_file(fmt="GIF", name="a.gif"))
        self.assertEqual(form.errors["photo"], ["Format harus JPG, PNG, atau WEBP."])

    def test_rejects_a_truncated_jpeg(self):
        whole = image_file(fmt="JPEG", size=(400, 400), name="a.jpg").read()
        form = self.form_with(SimpleUploadedFile("a.jpg", whole[: len(whole) // 2]))
        self.assertEqual(form.errors["photo"], ["Berkas harus berupa gambar."])

    def test_rejects_too_many_pixels(self):
        # Few bytes but huge once decoded, so the 5 MB limit can't catch it.
        form = self.form_with(image_file(size=(6000, 5000)))
        self.assertEqual(form.errors["photo"], ["Resolusi foto terlalu besar."])

    def test_valid_upload_can_still_be_saved_after_the_checks(self):
        form = self.form_with(image_file(fmt="JPEG", name="a.jpg"))
        self.assertTrue(form.is_valid(), form.errors)
        item = form.save(commit=False)
        item.owner = self.owner
        item.save()
        with Image.open(item.photo.path) as saved:
            self.assertEqual(saved.format, "WEBP")

    def test_rejects_a_photo_over_the_size_limit(self):
        photo = image_file()
        photo.size = 5 * 1024 * 1024 + 1
        form = self.form_with(photo)
        self.assertEqual(form.errors["photo"], ["Ukuran foto maksimal 5 MB."])


class ItemPhotoViewTests(PhotoTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.owner)

    def test_form_is_sent_as_multipart(self):
        response = self.client.get(reverse("katalog:item_create"), **HX)
        self.assertContains(response, 'enctype="multipart/form-data"')
        self.assertContains(response, 'hx-encoding="multipart/form-data"')
        self.assertContains(response, 'type="file"')
        self.assertNotContains(response, 'name="photo_url"')

    def test_create_with_upload_shows_the_photo_on_the_card(self):
        data = {**VALID_POST, "photo": image_file()}
        response = self.client.post(reverse("katalog:item_create"), data, **HX)
        item = Item.objects.get(name=VALID_POST["name"])
        self.assertTrue(item.photo)
        self.assertContains(response, item.photo.url)

    def test_edit_can_replace_the_photo(self):
        item = make_item(self.owner, photo=image_file())
        old_name = item.photo.name
        data = {**VALID_POST, "photo": image_file()}
        self.client.post(reverse("katalog:item_update", args=[item.pk]), data, **HX)
        item.refresh_from_db()
        self.assertNotEqual(item.photo.name, old_name)

    def test_edit_without_a_new_file_keeps_the_photo(self):
        item = make_item(self.owner, photo=image_file())
        old_name = item.photo.name
        self.client.post(reverse("katalog:item_update", args=[item.pk]), VALID_POST, **HX)
        item.refresh_from_db()
        self.assertEqual(item.photo.name, old_name)

    def test_edit_can_clear_the_photo(self):
        item = make_item(self.owner, photo=image_file())
        data = {**VALID_POST, "photo-clear": "on"}
        self.client.post(reverse("katalog:item_update", args=[item.pk]), data, **HX)
        item.refresh_from_db()
        self.assertFalse(item.photo)

    def test_invalid_upload_comes_back_as_422(self):
        data = {**VALID_POST, "photo": SimpleUploadedFile("a.png", b"bukan gambar")}
        response = self.client.post(reverse("katalog:item_create"), data, **HX)
        self.assertEqual(response.status_code, 422)
        self.assertContains(response, "Berkas harus berupa gambar.", status_code=422)

    def test_json_has_the_uploaded_photo_url(self):
        item = make_item(self.owner, photo=image_file())
        data = self.client.get(reverse("katalog:item_detail_json", args=[item.pk])).json()
        self.assertEqual(data["photo_url"], item.photo.url)
