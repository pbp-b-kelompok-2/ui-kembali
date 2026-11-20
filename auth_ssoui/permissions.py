from rest_framework.permissions import BasePermission

from .models import Profile


class IsProfileComplete(BasePermission):
    """Allow access only when the authenticated user has completed a profile."""

    message = "Lengkapi profil terlebih dahulu."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return Profile.objects.filter(user=user, is_complete=True).exists()


class IsProfileIncomplete(BasePermission):
    """Allow access only while the authenticated user still needs onboarding."""

    message = "Profil sudah lengkap."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return not Profile.objects.filter(user=user, is_complete=True).exists()
