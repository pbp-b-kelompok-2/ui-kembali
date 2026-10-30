"""Browser tests (Selenium + headless Chrome). They need Chrome and internet
(HTMX and Tailwind come from a CDN), so CI skips them:

    python manage.py test katalog --exclude-tag=functional
"""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import tag
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

from auth_ssoui.models import Profile
from katalog.models import Item

from .test_models import make_item

User = get_user_model()


@tag("functional")
class KatalogBrowserTests(StaticLiveServerTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        options = webdriver.ChromeOptions()
        options.add_argument("--headless=new")
        options.add_argument("--window-size=1280,900")
        cls.browser = webdriver.Chrome(options=options)

    @classmethod
    def tearDownClass(cls):
        cls.browser.quit()
        super().tearDownClass()

    def setUp(self):
        self.owner = User.objects.create_user("pemilik", password="pw")
        self.wait = WebDriverWait(self.browser, 10)

    def login(self, user):
        # Reuse Django's test login: copy its session cookie into the browser.
        self.client.force_login(user)
        self.browser.get(self.live_server_url + "/katalog/json/")
        self.browser.add_cookie({
            "name": settings.SESSION_COOKIE_NAME,
            "value": self.client.cookies[settings.SESSION_COOKIE_NAME].value,
            "path": "/",
        })

    def card_names(self):
        return [h.text for h in self.browser.find_elements(By.CSS_SELECTOR, "#item-list h3")]

    def test_live_search_filters_without_reload(self):
        make_item(self.owner, name="Kipas angin meja")
        make_item(self.owner, name="Buku kalkulus")
        self.browser.get(self.live_server_url + "/katalog/")
        self.browser.execute_script("window.notReloaded = true")

        self.browser.find_element(By.NAME, "q").send_keys("kipas")
        self.wait.until(lambda _: self.card_names() == ["Kipas angin meja"])

        self.assertIn("q=kipas", self.browser.current_url)
        self.assertTrue(self.browser.execute_script("return window.notReloaded"))

    def test_opening_the_edit_form_keeps_the_catalog_url(self):
        make_item(self.owner, name="Kipas angin meja")
        Profile.objects.create(user=self.owner, nama="Owen Pemilik", is_complete=True)
        self.login(self.owner)
        self.browser.get(self.live_server_url + "/katalog/")
        edit = self.browser.find_element(By.XPATH, "//button[contains(., 'Edit')]")
        # The page scrolls smoothly, so a normal click can land before it stops.
        self.browser.execute_script("arguments[0].click()", edit)

        self.wait.until(EC.visibility_of_element_located((By.ID, "item-form")))
        self.assertTrue(self.browser.current_url.endswith("/katalog/"))

    def test_owner_creates_an_item_in_the_modal(self):
        # The navbar's button only shows once the SSO profile is complete.
        Profile.objects.create(user=self.owner, nama="Owen Pemilik", is_complete=True)
        self.login(self.owner)
        self.browser.get(self.live_server_url + "/katalog/")
        self.browser.find_element(By.CSS_SELECTOR, "a.btn-pasang").click()

        form = self.wait.until(EC.visibility_of_element_located((By.ID, "item-form")))
        form.find_element(By.NAME, "name").send_keys("Rak sepatu")
        form.find_element(By.NAME, "description").send_keys("Rak sepatu tiga susun, kokoh.")
        Select(form.find_element(By.NAME, "category")).select_by_value("PERABOT")
        Select(form.find_element(By.NAME, "condition")).select_by_value("BAIK")
        form.find_element(By.NAME, "location_name").send_keys("Kukusan")
        form.find_element(By.NAME, "contact").send_keys("081234567890")
        form.find_element(By.CSS_SELECTOR, "button[type=submit]").click()

        self.wait.until(lambda _: "Rak sepatu" in self.card_names())
        self.wait.until(EC.text_to_be_present_in_element((By.ID, "toast-stack"), "berhasil"))
        self.assertTrue(Item.objects.filter(name="Rak sepatu", owner=self.owner).exists())
