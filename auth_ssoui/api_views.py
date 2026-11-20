from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Profile
from .permissions import IsProfileComplete, IsProfileIncomplete
from .serializers import ProfileCompletionSerializer, ProfileEditSerializer, ProfileSerializer


@api_view(["GET", "HEAD", "POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def profile_detail(request):
    """Return the authenticated user's profile, creating an empty one if needed."""
    profile, _ = Profile.objects.get_or_create(user=request.user)
    return Response(ProfileSerializer(profile, context={"request": request}).data)


@api_view(["PATCH", "POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsProfileComplete])
def profile_edit(request):
    """Update only the fields available in the normal profile edit form."""
    profile, _ = Profile.objects.get_or_create(user=request.user)
    serializer = ProfileEditSerializer(
        profile,
        data=request.data,
        partial=True,
        context={"request": request},
    )
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(ProfileSerializer(profile, context={"request": request}).data)


@api_view(["PATCH", "POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsProfileIncomplete])
def profile_complete(request):
    """Complete an SSO user's profile without accepting SSO-owned fields."""
    profile, _ = Profile.objects.get_or_create(user=request.user)
    serializer = ProfileCompletionSerializer(
        profile,
        data=request.data,
        partial=True,
        context={"request": request},
    )
    serializer.is_valid(raise_exception=True)
    serializer.save(is_complete=True, peran=profile.peran or "Mahasiswa")
    return Response(ProfileSerializer(profile, context={"request": request}).data)
