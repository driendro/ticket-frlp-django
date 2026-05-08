# apps/cron/management/commands/limpiar_compras_expiradas.py
import json
import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.pagos.models import CompraPendiente
from apps.comedor.services import es_fecha_vianda_ordenable

logger = logging.getLogger(__name__)

MINUTOS_EXPIRACION = 15


class Command(BaseCommand):
    help = 'Limpia compras pendientes expiradas'

    def handle(self, *args, **kwargs):
        self.stdout.write('Iniciando limpieza de compras expiradas...')

        compras = CompraPendiente.objects.filter(
            mp_estado='pasarela',
            procesada=False,
        )

        if not compras.exists():
            self.stdout.write('No hay compras en pasarela.')
            return

        ahora = timezone.now()
        expiradas = 0

        for compra in compras:
            expirar = False

            # Verificar por tiempo
            limite = compra.created_at + timedelta(minutes=MINUTOS_EXPIRACION)
            if ahora > limite:
                expirar = True
                self.stdout.write(
                    f'  Compra {compra.id} expirada por tiempo.'
                )

            # Verificar por fecha de vianda
            if not expirar:
                try:
                    viandas = json.loads(compra.datos)
                    for vianda in viandas:
                        if not es_fecha_vianda_ordenable(vianda['dia_comprado']):
                            expirar = True
                            self.stdout.write(
                                f'  Compra {compra.id} expirada por fecha de vianda.'
                            )
                            break
                except Exception as e:
                    logger.error(
                        f'Error parseando viandas compra {compra.id}: {e}')
                    expirar = True

            if expirar:
                compra.mp_estado = 'expired_by_cronjob'
                compra.save(update_fields=['mp_estado'])
                expiradas += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Limpieza finalizada. {expiradas} compras expiradas.'
            )
        )
