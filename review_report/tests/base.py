from django.contrib.auth import get_user_model
from django.test import TestCase
from katalog.models import Item, ItemRequest


class ModuleCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.owner = User.objects.create_user('seller')
        cls.buyer = User.objects.create_user('buyer')
        cls.other = User.objects.create_user('other')
        cls.item = cls.make_item(cls.owner)
        cls.deal = ItemRequest.objects.create(item=cls.item, requester=cls.buyer, status='SELESAI')

    @staticmethod
    def make_item(owner, **kwargs):
        values = dict(owner=owner, name='Meja belajar', description='Meja layak pakai untuk kost',
                      category='PERABOT', condition='BAIK', location_name='Depok', contact='08123456789')
        values.update(kwargs)
        return Item.objects.create(**values)
