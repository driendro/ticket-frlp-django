# apps/cron/management/commands/consultar_estado_mp.py
import logging
import mercadopago

from django.core.management.base import BaseCommand
from django.conf import settings

from apps.pagos.models import CompraPendiente
from apps.pagos.services import procesar_pago_aprobado, procesar_pago_rechazado

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Consulta el estado de pagos pendientes en Mercado Pago'

    def handle(self, *args, **kwargs):
        self.stdout.write('Iniciando consulta de estados MP...')

        if not settings.MP_ACCESS_TOKEN:
            self.stdout.write(
                self.style.ERROR('MP_ACCESS_TOKEN no configurado.')
            )
            return

        sdk = mercadopago.SDK(settings.MP_ACCESS_TOKEN)

        compras = CompraPendiente.objects.filter(
            mp_estado__in=['pending', 'in_process', 'pasarela'],
            procesada=False,
        )

        if not compras.exists():
            self.stdout.write('No hay compras pendientes.')
            return

        self.stdout.write(f'Procesando {compras.count()} compras...')

        for compra in compras:
            self.stdout.write(
                f'Consultando: {compra.external_reference}'
            )
            try:
                filters = {"external_reference": compra.external_reference}
                result = sdk.payment().search({"filters": filters})
                payments = result.get('response', {}).get('results', [])

                if not payments:
                    self.stdout.write(
                        f'  Sin pagos para {compra.external_reference}'
                    )
                    continue

                aprobado = False
                for payment in payments:
                    estado = payment.get('status')
                    detalle = payment.get('status_detail', '')

                    self.stdout.write(
                        f'  Pago {payment.get("id")} - Estado: {estado}'
                    )

                    if estado == 'approved' and not aprobado:
                        if procesar_pago_aprobado(compra, payment):
                            aprobado = True
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f'  Aprobado: {compra.external_reference}'
                                )
                            )

                    elif estado in ['rejected', 'cancelled'] and not aprobado:
                        if procesar_pago_rechazado(compra, payment):
                            self.stdout.write(
                                self.style.WARNING(
                                    f'  Rechazado: {compra.external_reference}'
                                )
                            )

            except Exception as e:
                logger.error(
                    f'Error procesando {compra.external_reference}: {e}'
                )
                self.stdout.write(
                    self.style.ERROR(f'  Error: {e}')
                )

        self.stdout.write(
            self.style.SUCCESS('Consulta de estados finalizada.')
        )
