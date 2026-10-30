"""Opt-in Chrome functional tests: RUN_BROWSER_TESTS=1 manage.py test ...test_browser.

Real browser + live Django + real CSRF/HTMX. No SSO/Nominatim calls. Requires
Chrome and Selenium; CDN availability is needed just as for the catalog UI.
Screenshots contain only synthetic test data and go into ignored .artifacts/.
"""
import os
import base64
from pathlib import Path
from unittest import skipUnless
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import tag
from django.urls import reverse
from auth_ssoui.models import Profile
from katalog.models import ItemRequest
from review_report.models import Review, Report
from review_report.tests.base import ModuleCase


@tag('browser')
@skipUnless(os.environ.get('RUN_BROWSER_TESTS') == '1', 'Set RUN_BROWSER_TESTS=1 for Chrome functional tests')
class BrowserTests(StaticLiveServerTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        os.environ.setdefault('SE_CACHE_PATH', str(settings.BASE_DIR / '.browser-cache'))
        options = Options()
        options.add_argument('--headless=new')
        options.add_argument('--window-size=1440,1200')
        cls.browser = webdriver.Chrome(options=options)
        cls.addClassCleanup(cls.browser.quit)

    def setUp(self):
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.common.exceptions import StaleElementReferenceException
        self.wait = WebDriverWait(self.browser, 20, ignored_exceptions=(StaleElementReferenceException,))
        self.browser.delete_all_cookies()
        User = get_user_model()
        self.owner = User.objects.create_user('penjual-demo')
        self.buyer = User.objects.create_user('pembeli-demo')
        Profile.objects.create(user=self.buyer, nama='Pembeli Demo', is_complete=True)
        self.item = ModuleCase.make_item(self.owner)
        self.deal = ItemRequest.objects.create(item=self.item, requester=self.buyer, status='SELESAI')
        self.client.force_login(self.buyer)
        self.browser.get(self.live_server_url + reverse('review_report:owner_reviews', args=[self.owner.pk]))
        self.browser.add_cookie({'name': settings.SESSION_COOKIE_NAME, 'value': self.client.cookies[settings.SESSION_COOKIE_NAME].value, 'path': '/'})

    def open(self, name, *args):
        self.browser.get(self.live_server_url + reverse('review_report:' + name, args=args))
        self.wait.until(lambda d: d.execute_script('return !!window.htmx'))

    def find(self, selector):
        from selenium.webdriver.common.by import By
        return self.browser.find_element(By.CSS_SELECTOR, selector)

    def click(self, selector):
        element = self.find(selector)
        self.browser.execute_script("arguments[0].scrollIntoView({block:'center'})", element)
        element.click()

    def screenshot(self, name):
        output = Path(settings.BASE_DIR) / '.artifacts' / 'review_report'
        output.mkdir(parents=True, exist_ok=True)
        width, height = self.browser.execute_script('return [document.documentElement.clientWidth, document.documentElement.scrollHeight]')
        png = self.browser.execute_cdp_cmd('Page.captureScreenshot', {'captureBeyondViewport': True, 'clip': {'x': 0, 'y': 0, 'width': width, 'height': height, 'scale': 1}})
        (output / f'{name}.png').write_bytes(base64.b64decode(png['data']))

    def test_saving_indicator_and_disabled_submit(self):
        from threading import Event
        from unittest.mock import patch
        from selenium.webdriver.support.ui import WebDriverWait
        from review_report import services
        self.open('review_create', self.deal.pk)
        self.click('input[name=rating][value="5"]')
        self.find('textarea[name=comment]').send_keys('Transaksi berjalan baik dan barang sesuai.')
        release = Event()
        original = services.create_review

        def paused_create(*args, **kwargs):
            release.wait(10)
            return original(*args, **kwargs)

        with patch('review_report.services.create_review', side_effect=paused_create):
            try:
                self.click('#rr-content button[type=submit]')
                WebDriverWait(self.browser, 3).until(lambda d: not self.find('#rr-content button[type=submit]').is_enabled())
                self.assertTrue(self.find('.rr-saving').is_displayed())
            finally:
                release.set()
            self.wait.until(lambda d: Review.objects.exists() and '/ulasan/' in d.current_url)

    def test_review_htmx_crud_validation_keyboard_and_responsive_layout(self):
        from selenium.webdriver.common.keys import Keys
        self.open('review_create', self.deal.pk)
        self.wait.until(lambda d: d.execute_script("return getComputedStyle(document.querySelector('.rr-module')).backgroundColor") == 'rgb(247, 246, 241)')
        self.screenshot('review-desktop')
        # Remove only browser validation to exercise server validation over HTMX.
        self.browser.execute_script("document.querySelector('#rr-content form').noValidate = true")
        self.click('#rr-content button[type=submit]')
        self.wait.until(lambda d: self.find('[role=alert]').is_displayed())
        radio = self.find('input[name=rating][value="4"]')
        radio.send_keys(Keys.SPACE)
        self.find('textarea[name=comment]').send_keys('Penjual ramah dan barang sesuai deskripsi.')
        self.click('#rr-content button[type=submit]')
        self.wait.until(lambda d: '/ulasan/' in d.current_url and Review.objects.exists())
        self.assertEqual(Review.objects.get().rating, 4)
        self.wait.until(lambda d: 'Ulasan berhasil dikirim.' in self.find('#toast-stack').text)
        self.assertEqual(len(self.browser.find_elements('css selector', 'html')), 1)
        self.click('#rr-content a[hx-get]')
        self.wait.until(lambda d: d.current_url.endswith('/edit/'))
        comment = self.find('textarea[name=comment]')
        comment.clear()
        comment.send_keys('Ulasan diperbarui setelah transaksi selesai.')
        self.click('#rr-content button[type=submit]')
        self.wait.until(lambda d: 'Ulasan diperbarui' in self.find('#rr-content').text and not d.current_url.endswith('/edit/'))
        self.click('#rr-content form[hx-confirm] button')
        self.wait.until(lambda d: d.switch_to.alert).accept()
        self.wait.until(lambda d: not Review.objects.exists())
        self.assertIn('Belum ada ulasan', self.find('#rr-content').text)
        self.open('review_create', self.deal.pk)
        try:
            for width, name in [(390, 'review-mobile'), (768, 'review-tablet')]:
                self.browser.execute_cdp_cmd('Emulation.setDeviceMetricsOverride', {'width': width, 'height': 844, 'deviceScaleFactor': 1, 'mobile': True})
                self.screenshot(name)
                self.assertLessEqual(self.browser.execute_script('return document.documentElement.scrollWidth'), width)
            icons = self.browser.execute_script("return Array.from(document.querySelectorAll('.rr-module img[src*=\"/icons/\"]')).map(i => [i.naturalWidth, i.width, i.naturalHeight, i.height])")
            self.assertTrue(icons)
            for natural_width, width, natural_height, height in icons:
                self.assertGreater(natural_width, 0)
                self.assertEqual((width, height), (natural_width, natural_height))
        finally:
            self.browser.execute_cdp_cmd('Emulation.clearDeviceMetricsOverride', {})

    def test_report_htmx_crud_filter_and_status_lock(self):
        from selenium.webdriver.support.ui import Select
        from review_report import services
        self.open('report_item', self.item.pk)
        self.find('textarea[name=description]').send_keys('Barang berbeda dengan deskripsi yang ditampilkan.')
        self.click('#rr-content button[type=submit]')
        self.wait.until(lambda d: Report.objects.exists() and '/laporan/' in d.current_url)
        self.screenshot('report-detail')
        self.click('#rr-content a[hx-get]')
        self.wait.until(lambda d: d.current_url.endswith('/edit/'))
        Select(self.find('select[name=category]')).select_by_value('MISLEADING')
        self.click('#rr-content button[type=submit]')
        self.wait.until(lambda d: 'Deskripsi menyesatkan' in self.find('#rr-content').text)
        self.click('#rr-content form[hx-confirm] button')
        self.wait.until(lambda d: d.switch_to.alert).accept()
        self.wait.until(lambda d: not Report.objects.exists())
        report = services.create_report(self.buyer, target_user=self.owner, category='SPAM', description='Pesan spam yang terus dikirimkan berulang.')
        self.owner.is_staff = self.owner.is_superuser = True
        self.owner.save()
        services.moderate_report(report, self.owner, 'IN_REVIEW', internal_notes='Catatan rahasia internal')
        self.open('my_reports')
        Select(self.find('#status-filter')).select_by_value('PENDING')
        self.click('#rr-content form button')
        self.wait.until(lambda d: 'Belum ada laporan' in self.find('#rr-content').text)
        self.open('report_detail', report.pk)
        self.assertIn('tidak dapat diedit', self.find('#rr-content').text)
        self.assertNotIn('Catatan rahasia', self.find('#rr-content').text)
        self.assertFalse(self.browser.find_elements('css selector', '#rr-content form'))
