from django import forms

from .models import Comment, ForumPost


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    widget = MultipleFileInput

    def clean(self, data, initial=None):
        if isinstance(data, (list, tuple)):
            return [super(MultipleFileField, self).clean(item, initial) for item in data]
        if data:
            return [super().clean(data, initial)]
        return []


class ForumPostForm(forms.ModelForm):
    attachments = MultipleFileField(
        required=False,
        label="Lampiran (opsional)",
        help_text="Pilih satu atau beberapa gambar atau file.",
    )

    class Meta:
        model = ForumPost
        fields = ["title", "category", "content"]
        labels = {
            "title": "Judul diskusi",
            "category": "Kategori",
            "content": "Isi diskusi",
        }
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "Tulis judul diskusi..."}),
            "content": forms.Textarea(
                attrs={"rows": 8, "placeholder": "Ceritakan sesuatu kepada komunitas..."}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "forum-input"


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ["content"]
        labels = {"content": "Komentar"}
        widgets = {
            "content": forms.Textarea(
                attrs={"rows": 3, "placeholder": "Tulis komentar..."}
            )
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["content"].widget.attrs["class"] = "forum-input"
