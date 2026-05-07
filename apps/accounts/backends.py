# apps/accounts/backends.py
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model

User = get_user_model()


class DocumentoBackend(ModelBackend):
    """
    Autenticación por número de documento en lugar de username.
    """

    def authenticate(self, request, documento=None, password=None, **kwargs):
        try:
            user = User.objects.get(documento=documento)
        except User.DoesNotExist:
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user

        return None
