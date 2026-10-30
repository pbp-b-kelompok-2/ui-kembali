from django.test import TestCase

from katalog.forms import ItemForm
from katalog.models import Item


def form_data(**overrides):
    data = {
        "name": "Rice cooker",
        "description": "Rice cooker 1 liter, masih normal semua fungsinya.",
        "category": Item.Category.DAPUR,
        "condition": Item.Condition.SEPERTI_BARU,
        "location_name": "Pondok Cina",
        "transaction_type": Item.TransactionType.ADOPSI,
        "price": "",
        "contact": "081234567890",
    }
    data.update(overrides)
    return data


class ItemFormTests(TestCase):
    def test_valid_adopsi(self):
        form = ItemForm(data=form_data())
        self.assertTrue(form.is_valid(), form.errors)

    def test_valid_jual(self):
        form = ItemForm(
            data=form_data(transaction_type=Item.TransactionType.JUAL, price="75000")
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_name_min_length(self):
        form = ItemForm(data=form_data(name="ab"))
        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors)

    def test_description_min_length(self):
        form = ItemForm(data=form_data(description="pendek"))
        self.assertFalse(form.is_valid())
        self.assertIn("description", form.errors)

    def test_jual_without_price_is_invalid(self):
        form = ItemForm(data=form_data(transaction_type=Item.TransactionType.JUAL))
        self.assertFalse(form.is_valid())
        self.assertIn("price", form.errors)

    def test_adopsi_with_price_is_invalid(self):
        form = ItemForm(data=form_data(price="1000"))
        self.assertFalse(form.is_valid())
        self.assertIn("price", form.errors)

    def test_required_message_is_indonesian(self):
        form = ItemForm(data=form_data(name="", contact=""))
        self.assertEqual(form.errors["name"], ["Wajib diisi."])
        self.assertEqual(form.errors["contact"], ["Wajib diisi."])

    def test_html_is_stripped_from_text_fields(self):
        form = ItemForm(
            data=form_data(
                name="<b>Rice</b> cooker",
                description="<script>alert(1)</script>Rice cooker masih normal.",
                location_name="<i>Pondok Cina</i>",
            )
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["name"], "Rice cooker")
        self.assertNotIn("<", form.cleaned_data["description"])
        self.assertEqual(form.cleaned_data["location_name"], "Pondok Cina")

    def test_name_that_is_only_html_is_too_short(self):
        form = ItemForm(data=form_data(name="<b></b>ab"))
        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors)

    def test_owner_and_status_are_not_editable(self):
        self.assertNotIn("owner", ItemForm.base_fields)
        self.assertNotIn("status", ItemForm.base_fields)
        self.assertNotIn("is_deleted", ItemForm.base_fields)
