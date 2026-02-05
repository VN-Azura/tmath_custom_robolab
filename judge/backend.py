from django.contrib.auth.backends import ModelBackend
from django.utils import timezone


class CustomAuthBackend(ModelBackend):
    def authenticate(self, request, username, password, **kwargs):
        user = super().authenticate(request, username, password, **kwargs)
        if user is not None:
            if user.profile.expiration_date is not None and user.profile.expiration_date < timezone.now():
                return None
        return user
