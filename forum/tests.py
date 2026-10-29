from pathlib import Path
from tempfile import TemporaryDirectory
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .forms import ForumPostForm
from .models import Comment, ForumAttachment, ForumPost


User = get_user_model()


class ForumAttachmentTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.media_directory = TemporaryDirectory()
        cls.media_settings = override_settings(MEDIA_ROOT=cls.media_directory.name)
        cls.media_settings.enable()

    @classmethod
    def tearDownClass(cls):
        cls.media_settings.disable()
        cls.media_directory.cleanup()
        super().tearDownClass()

    def setUp(self):
        self.owner = User.objects.create_user(username="forum-owner", password="pass12345")
        self.other_user = User.objects.create_user(username="forum-other", password="pass12345")
        self.post = ForumPost.objects.create(
            title="Diskusi tes",
            content="Isi diskusi tes",
            author=self.owner,
        )

    @staticmethod
    def uploaded_file(name="document.pdf", content=b"file contents"):
        return SimpleUploadedFile(name, content, content_type="application/octet-stream")

    def create_attachment(self, name="document.pdf"):
        return ForumAttachment.objects.create(
            post=self.post,
            file=self.uploaded_file(name),
        )

    def test_attachment_field_accepts_multiple_files(self):
        form = ForumPostForm(
            data={
                "title": "Diskusi baru",
                "content": "Isi diskusi",
                "category": ForumPost.Category.LAINNYA,
            },
            files={
                "attachments": [
                    self.uploaded_file("one.pdf"),
                    self.uploaded_file("two.png"),
                ]
            },
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(len(form.cleaned_data["attachments"]), 2)

    def test_post_create_saves_multiple_attachments(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("forum:post_create"),
            {
                "title": "Diskusi dengan file",
                "category": ForumPost.Category.LAINNYA,
                "content": "Dua file dilampirkan",
                "attachments": [
                    self.uploaded_file("notes.pdf"),
                    self.uploaded_file("photo.png"),
                ],
            },
        )

        created_post = ForumPost.objects.get(title="Diskusi dengan file")
        self.assertRedirects(
            response,
            reverse("forum:post_detail", args=[created_post.pk]),
        )
        self.assertEqual(created_post.attachments.count(), 2)

    def test_detail_shows_each_attachment(self):
        self.create_attachment("first.pdf")
        self.create_attachment("second.png")

        response = self.client.get(reverse("forum:post_detail", args=[self.post.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "first.pdf")
        self.assertContains(response, "second.png")
        self.assertContains(response, "data-open-image")

    def test_owner_can_delete_attachment_immediately(self):
        attachment = self.create_attachment()
        stored_path = Path(attachment.file.path)
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse(
                "forum:attachment_delete",
                args=[self.post.pk, str(attachment.pk)],
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"deleted": True})
        self.assertFalse(ForumAttachment.objects.filter(pk=attachment.pk).exists())
        self.assertFalse(stored_path.exists())

    def test_other_user_cannot_delete_attachment(self):
        attachment = self.create_attachment()
        stored_path = Path(attachment.file.path)
        self.client.force_login(self.other_user)

        response = self.client.post(
            reverse(
                "forum:attachment_delete",
                args=[self.post.pk, str(attachment.pk)],
            )
        )

        self.assertEqual(response.status_code, 403)
        self.assertTrue(ForumAttachment.objects.filter(pk=attachment.pk).exists())
        self.assertTrue(stored_path.exists())

    def test_owner_can_delete_legacy_attachment(self):
        self.post.attachment.save("legacy.pdf", self.uploaded_file("legacy.pdf"))
        stored_path = Path(self.post.attachment.path)
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("forum:attachment_delete", args=[self.post.pk, "legacy"])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"deleted": True})
        self.post.refresh_from_db()
        self.assertFalse(self.post.attachment)
        self.assertFalse(stored_path.exists())


class ForumPostAndInteractionTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="post-owner", password="pass12345")
        self.other_user = User.objects.create_user(username="post-other", password="pass12345")
        self.post = ForumPost.objects.create(
            title="Kipas untuk kamar kos",
            content="Rekomendasi kipas yang hemat listrik",
            category=ForumPost.Category.TIPS,
            author=self.owner,
        )
        self.other_post = ForumPost.objects.create(
            title="Cari buku bekas",
            content="Ada yang punya buku bekas?",
            category=ForumPost.Category.TANYA,
            author=self.other_user,
        )

    @staticmethod
    def post_form_data(**overrides):
        data = {
            "title": "Judul posting",
            "category": ForumPost.Category.LAINNYA,
            "content": "Isi posting",
        }
        data.update(overrides)
        return data

    def test_forum_list_search_matches_title_and_content(self):
        response = self.client.get(reverse("forum:forum_list"), {"q": "hemat listrik"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["posts"]), [self.post])
        self.assertEqual(response.context["query"], "hemat listrik")

    def test_forum_list_filters_by_category_and_ignores_invalid_category(self):
        category_response = self.client.get(
            reverse("forum:forum_list"),
            {"category": ForumPost.Category.TIPS},
        )
        invalid_response = self.client.get(
            reverse("forum:forum_list"),
            {"category": "UNKNOWN"},
        )

        self.assertEqual(list(category_response.context["posts"]), [self.post])
        self.assertEqual(category_response.context["selected_category"], ForumPost.Category.TIPS)
        self.assertEqual(invalid_response.context["selected_category"], "")
        self.assertEqual(invalid_response.context["post_count"], 2)

    def test_forum_list_sorts_oldest_and_most_popular(self):
        base_time = timezone.now()
        ForumPost.objects.filter(pk=self.other_post.pk).update(created_at=base_time - timedelta(days=1))
        ForumPost.objects.filter(pk=self.post.pk).update(created_at=base_time)
        self.post.liked_by.add(self.other_user)

        oldest_response = self.client.get(reverse("forum:forum_list"), {"sort": "oldest"})
        popular_response = self.client.get(reverse("forum:forum_list"), {"sort": "popular"})

        self.assertEqual(list(oldest_response.context["posts"]), [self.other_post, self.post])
        self.assertEqual(list(popular_response.context["posts"]), [self.post, self.other_post])
        self.assertEqual(popular_response.context["selected_sort"], "popular")

    def test_forum_list_paginates_four_posts_per_page(self):
        for index in range(4):
            ForumPost.objects.create(
                title=f"Posting tambahan {index}",
                content="Isi",
                author=self.owner,
            )

        first_page = self.client.get(reverse("forum:forum_list"))
        second_page = self.client.get(reverse("forum:forum_list"), {"page": 2})

        self.assertEqual(first_page.context["post_count"], 6)
        self.assertEqual(len(first_page.context["posts"]), 4)
        self.assertTrue(first_page.context["page_obj"].has_next())
        self.assertEqual(len(second_page.context["posts"]), 2)

    def test_post_detail_returns_404_for_missing_post(self):
        response = self.client.get(reverse("forum:post_detail", args=[999999]))

        self.assertEqual(response.status_code, 404)

    def test_forum_list_filters_my_and_saved_posts(self):
        self.client.force_login(self.owner)
        self.other_post.saved_by.add(self.owner)

        mine_response = self.client.get(reverse("forum:forum_list"), {"mine": "1"})
        saved_response = self.client.get(reverse("forum:forum_list"), {"saved": "1"})

        self.assertEqual(list(mine_response.context["posts"]), [self.post])
        self.assertEqual(list(saved_response.context["posts"]), [self.other_post])

    def test_post_create_requires_login(self):
        response = self.client.get(reverse("forum:post_create"))

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith("/auth/login/"))

    def test_post_create_rejects_invalid_form(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("forum:post_create"),
            self.post_form_data(title=""),
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.assertFalse(ForumPost.objects.filter(title="").exists())

    def test_post_create_saves_valid_post(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("forum:post_create"),
            self.post_form_data(title="Posting baru"),
        )

        created = ForumPost.objects.get(title="Posting baru")
        self.assertRedirects(response, reverse("forum:post_detail", args=[created.pk]))
        self.assertEqual(created.author, self.owner)

    def test_owner_can_edit_post(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("forum:post_update", args=[self.post.pk]),
            self.post_form_data(title="Judul sudah diperbarui"),
        )

        self.post.refresh_from_db()
        self.assertRedirects(response, reverse("forum:post_detail", args=[self.post.pk]))
        self.assertEqual(self.post.title, "Judul sudah diperbarui")

    def test_post_edit_requires_login(self):
        response = self.client.get(reverse("forum:post_update", args=[self.post.pk]))

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith("/auth/login/"))

    def test_invalid_edit_does_not_change_post(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("forum:post_update", args=[self.post.pk]),
            self.post_form_data(title=""),
        )

        self.post.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.assertEqual(self.post.title, "Kipas untuk kamar kos")

    def test_other_user_cannot_edit_post(self):
        self.client.force_login(self.other_user)

        response = self.client.post(
            reverse("forum:post_update", args=[self.post.pk]),
            self.post_form_data(title="Perubahan tanpa izin"),
        )

        self.post.refresh_from_db()
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.post.title, "Kipas untuk kamar kos")

    def test_owner_can_delete_post_and_its_comments(self):
        comment = Comment.objects.create(post=self.post, author=self.other_user, content="Komentar")
        self.client.force_login(self.owner)

        response = self.client.post(reverse("forum:post_delete", args=[self.post.pk]))

        self.assertRedirects(response, reverse("forum:forum_list"))
        self.assertFalse(ForumPost.objects.filter(pk=self.post.pk).exists())
        self.assertFalse(Comment.objects.filter(pk=comment.pk).exists())

    def test_other_user_cannot_delete_post(self):
        self.client.force_login(self.other_user)

        response = self.client.post(reverse("forum:post_delete", args=[self.post.pk]))

        self.assertEqual(response.status_code, 403)
        self.assertTrue(ForumPost.objects.filter(pk=self.post.pk).exists())

    def test_post_delete_only_accepts_post_method(self):
        self.client.force_login(self.owner)

        response = self.client.get(reverse("forum:post_delete", args=[self.post.pk]))

        self.assertEqual(response.status_code, 405)
        self.assertTrue(ForumPost.objects.filter(pk=self.post.pk).exists())

    def test_comment_create_and_reply(self):
        self.client.force_login(self.other_user)

        comment_response = self.client.post(
            reverse("forum:comment_create", args=[self.post.pk]),
            {"content": "Komentar pertama"},
        )
        comment = Comment.objects.get(content="Komentar pertama")
        reply_response = self.client.post(
            reverse("forum:comment_create", args=[self.post.pk]),
            {"content": "Balasan komentar", "parent": comment.pk},
        )

        reply = Comment.objects.get(content="Balasan komentar")
        self.assertRedirects(comment_response, reverse("forum:post_detail", args=[self.post.pk]))
        self.assertRedirects(reply_response, reverse("forum:post_detail", args=[self.post.pk]))
        self.assertEqual(comment.author, self.other_user)
        self.assertEqual(reply.parent, comment)

    def test_comment_create_requires_login_and_ignores_empty_content(self):
        login_response = self.client.post(
            reverse("forum:comment_create", args=[self.post.pk]),
            {"content": "Anonim"},
        )
        self.assertEqual(login_response.status_code, 302)
        self.assertFalse(Comment.objects.filter(content="Anonim").exists())

        self.client.force_login(self.other_user)
        response = self.client.post(
            reverse("forum:comment_create", args=[self.post.pk]),
            {"content": "   "},
        )
        self.assertRedirects(response, reverse("forum:post_detail", args=[self.post.pk]))
        self.assertFalse(Comment.objects.filter(post=self.post).exists())

    def test_comment_reply_must_belong_to_same_post(self):
        foreign_comment = Comment.objects.create(
            post=self.other_post,
            author=self.other_user,
            content="Komentar di posting lain",
        )
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("forum:comment_create", args=[self.post.pk]),
            {"content": "Balasan lintas posting", "parent": foreign_comment.pk},
        )

        self.assertEqual(response.status_code, 404)
        self.assertFalse(Comment.objects.filter(content="Balasan lintas posting").exists())

    def test_post_like_toggles_for_authenticated_user(self):
        self.client.force_login(self.other_user)
        url = reverse("forum:post_like", args=[self.post.pk])

        first_response = self.client.post(url)
        self.assertTrue(self.post.liked_by.filter(pk=self.other_user.pk).exists())
        second_response = self.client.post(url)

        self.assertRedirects(first_response, reverse("forum:post_detail", args=[self.post.pk]))
        self.assertRedirects(second_response, reverse("forum:post_detail", args=[self.post.pk]))
        self.assertFalse(self.post.liked_by.filter(pk=self.other_user.pk).exists())

    def test_like_endpoints_require_login(self):
        comment = Comment.objects.create(post=self.post, author=self.owner, content="Komentar")

        post_like_response = self.client.post(reverse("forum:post_like", args=[self.post.pk]))
        comment_like_response = self.client.post(reverse("forum:comment_like", args=[comment.pk]))
        save_response = self.client.post(reverse("forum:post_save_toggle", args=[self.post.pk]))

        self.assertEqual(post_like_response.status_code, 302)
        self.assertEqual(comment_like_response.status_code, 302)
        self.assertEqual(save_response.status_code, 302)
        self.assertFalse(self.post.liked_by.exists())
        self.assertFalse(comment.liked_by.exists())
        self.assertFalse(self.post.saved_by.exists())

    def test_comment_like_toggles(self):
        comment = Comment.objects.create(post=self.post, author=self.owner, content="Komentar")
        self.client.force_login(self.other_user)
        url = reverse("forum:comment_like", args=[comment.pk])

        self.client.post(url)
        self.assertTrue(comment.liked_by.filter(pk=self.other_user.pk).exists())
        self.client.post(url)
        self.assertFalse(comment.liked_by.filter(pk=self.other_user.pk).exists())

    def test_save_toggle_and_saved_list(self):
        self.client.force_login(self.owner)
        url = reverse("forum:post_save_toggle", args=[self.other_post.pk])

        response = self.client.post(url, {"next": reverse("forum:forum_list") + "?saved=1"})
        self.assertRedirects(response, reverse("forum:forum_list") + "?saved=1")
        self.assertTrue(self.other_post.saved_by.filter(pk=self.owner.pk).exists())
        self.assertEqual(
            list(self.client.get(reverse("forum:forum_list"), {"saved": "1"}).context["posts"]),
            [self.other_post],
        )

        self.client.post(url)
        self.assertFalse(self.other_post.saved_by.filter(pk=self.owner.pk).exists())

    def test_save_toggle_rejects_external_redirect(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("forum:post_save_toggle", args=[self.post.pk]),
            {"next": "https://example.invalid/"},
        )

        self.assertRedirects(response, reverse("forum:post_detail", args=[self.post.pk]))

    def test_like_endpoints_reject_external_redirects(self):
        comment = Comment.objects.create(post=self.post, author=self.owner, content="Komentar")
        self.client.force_login(self.other_user)

        post_response = self.client.post(
            reverse("forum:post_like", args=[self.post.pk]),
            {"next": "https://example.invalid/"},
        )
        comment_response = self.client.post(
            reverse("forum:comment_like", args=[comment.pk]),
            {"next": "https://example.invalid/"},
        )

        self.assertRedirects(post_response, reverse("forum:post_detail", args=[self.post.pk]))
        self.assertRedirects(comment_response, reverse("forum:post_detail", args=[self.post.pk]))

    def test_comment_sort_orders_root_comments(self):
        older = Comment.objects.create(post=self.post, author=self.owner, content="Komentar lama")
        newer = Comment.objects.create(post=self.post, author=self.other_user, content="Komentar baru")
        newer.liked_by.add(self.owner)

        newest_response = self.client.get(
            reverse("forum:post_detail", args=[self.post.pk]),
            {"comment_sort": "newest"},
        )
        popular_response = self.client.get(
            reverse("forum:post_detail", args=[self.post.pk]),
            {"comment_sort": "popular"},
        )

        self.assertEqual(newest_response.context["comments"], [newer, older])
        self.assertEqual(popular_response.context["comments"], [newer, older])
