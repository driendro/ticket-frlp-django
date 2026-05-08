# apps/cron/management/commands/limpiar_logs.py
import os
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = 'Elimina archivos de log con más de 2 meses de antigüedad'

    def handle(self, *args, **kwargs):
        log_path = settings.LOGS_DIR if hasattr(settings, 'LOGS_DIR') \
            else settings.BASE_DIR / 'logs'

        if not os.path.isdir(log_path):
            self.stdout.write('Directorio de logs no encontrado.')
            return

        limite = datetime.now() - timedelta(days=60)
        eliminados = 0

        for archivo in os.listdir(log_path):
            ruta = os.path.join(log_path, archivo)
            if not os.path.isfile(ruta):
                continue

            fecha_mod = datetime.fromtimestamp(os.path.getmtime(ruta))
            if fecha_mod < limite:
                os.remove(ruta)
                eliminados += 1
                self.stdout.write(f'  Eliminado: {archivo}')

        self.stdout.write(
            self.style.SUCCESS(
                f'Limpieza finalizada. {eliminados} archivos eliminados.'
            )
        )
