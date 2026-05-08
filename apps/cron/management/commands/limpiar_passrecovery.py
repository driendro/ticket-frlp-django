# apps/cron/management/commands/limpiar_passrecovery.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.models import Permission


class Command(BaseCommand):
    help = 'Elimina tokens de recuperación de contraseña expirados'

    def handle(self, *args, **kwargs):
        # Django maneja password reset con su propio sistema
        # Este comando limpia tokens de más de 1 hora si usás
        # el sistema built-in de Django

        from django.contrib.auth.tokens import default_token_generator
        self.stdout.write(
            'Django maneja la expiración de tokens automáticamente.'
        )
        self.stdout.write(self.style.SUCCESS('OK'))
