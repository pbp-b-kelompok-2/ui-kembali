from functools import wraps
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from .models import Profile

def profile_required(view):
    @wraps(view)
    @login_required
    def wrapper(request, *args, **kwargs):
        profile, _ = Profile.objects.get_or_create(user=request.user)
        if not profile.is_complete:
            return redirect("main:lengkapi_profil")
        return view(request, *args, **kwargs)
    return wrapper