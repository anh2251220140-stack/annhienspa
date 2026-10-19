from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.db.models import Q

class IdentifierBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        User = get_user_model()
        if username is None or password is None:
            return None
        matches = list(User.objects.filter(Q(username__iexact=username.strip()) | Q(email__iexact=username.strip()))[:2])
        if len(matches) != 1:
            User().set_password(password)  # Keep a password hash on missing/ambiguous users too.
            return None
        user = matches[0]
        if user.check_password(password) and self.user_can_authenticate(user) and user.role in User.Role.values:
            return user
