from rest_framework import serializers
from .models import Profile

class ProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    pfp_url = serializers.SerializerMethodField()

    class Meta:
        model = Profile
        fields = (
            "username",
            "nama",
            "peran",
            "faculty",
            "angkatan",
            "nama_panggilan",
            "no_hp",
            "pfp_url",
            "titik_favorit",
            "bio",
            "is_complete",
        )
        read_only_fields = fields

    def get_pfp_url(self, profile):
        if not profile.pfp:
            return ""
        request = self.context.get("request")
        return request.build_absolute_uri(profile.pfp.url) if request else profile.pfp.url


class _ProfileInputSerializer(serializers.ModelSerializer):
    """Shared upload checks for the separate fill and edit payloads."""

    MAX_PFP_BYTES = 2 * 1024 * 1024
    PFP_FORMATS = {"JPEG", "PNG", "WEBP"}

    def validate_pfp(self, value):
        if value is None:
            return value
        if value.size > self.MAX_PFP_BYTES:
            raise serializers.ValidationError("Ukuran foto maksimal 2 MB.")
        image = getattr(value, "image", None)
        image_format = (getattr(image, "format", "") or "").upper()
        if image_format not in self.PFP_FORMATS:
            raise serializers.ValidationError("Format harus JPG, PNG, atau WEBP.")
        return value


class ProfileEditSerializer(_ProfileInputSerializer):
    class Meta:
        model = Profile
        fields = ("nama_panggilan", "pfp", "no_hp", "titik_favorit", "bio")


class ProfileCompletionSerializer(_ProfileInputSerializer):
    class Meta:
        model = Profile
        # Nama, faculty, and angkatan are synchronized from UI SSO and cannot
        # be supplied or overwritten by the client.
        fields = ("nama_panggilan", "pfp", "no_hp", "titik_favorit", "bio")

    def validate(self, attrs):
        attrs = super().validate(attrs)
        profile = self.instance
        required = {
            "nama_panggilan": attrs.get("nama_panggilan", profile.nama_panggilan),
            "no_hp": attrs.get("no_hp", profile.no_hp),
            "angkatan": profile.angkatan,
        }
        errors = {
            field: "Wajib diisi."
            for field, value in required.items()
            if not value
        }
        if errors:
            raise serializers.ValidationError(errors)
        return attrs
