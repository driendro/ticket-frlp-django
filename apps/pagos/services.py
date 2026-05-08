# apps/pagos/services.py
import json
import logging
from datetime import datetime
import time as time_module

import mercadopago


from django.conf import settings
from django.db import transaction

from apps.comedor.models import Compra, LogCompra, Transaccion
from apps.comedor.services import es_fecha_vianda_ordenable
from .models import CompraPendiente

logger = logging.getLogger(__name__)


def crear_compra_pendiente(usuario, seleccion: list, total: float) -> CompraPendiente:
    """
    Guarda la selección de viandas como compra pendiente.
    Equivale a guardarCompraPendiente() de CI3.
    """
    external_reference = f"{usuario.id}-{int(datetime.now().timestamp() * 1000000)}"

    compra = CompraPendiente.objects.create(
        usuario=usuario,
        external_reference=external_reference,
        datos=json.dumps(seleccion),
        total=total,
    )
    return compra


def generar_preferencia_mp(compra_pendiente, usuario) -> dict | None:
    """
    Genera la preferencia de Mercado Pago.
    Retorna None si el saldo cubre todo.
    Retorna False si hay error.
    Retorna dict con init_point si hay diferencia a pagar.
    Equivale a generarPreferenciaConSaldo() de CI3.
    """
    saldo = usuario.saldo
    total = float(compra_pendiente.total)
    monto_a_pagar = total - float(saldo)

    if monto_a_pagar <= 0:
        return None

    try:
        sdk = mercadopago.SDK(settings.MP_ACCESS_TOKEN)

        preference_data = {
            "items": [{
                "title": f"Compra de menú - {usuario.nombre} {usuario.apellido}",
                "quantity": 1,
                "unit_price": round(monto_a_pagar, 2),
                "description": f"{usuario.nombre}{usuario.apellido}{usuario.documento}",
            }],
            "external_reference": compra_pendiente.external_reference,
            "back_urls": {
                "success": settings.MP_BACK_URL_SUCCESS,
                "failure": settings.MP_BACK_URL_FAILURE,
                "pending": settings.MP_BACK_URL_PENDING,
            },
            "auto_return": "approved",
            "notification_url": settings.MP_NOTIFICATION_URL,
            "payment_methods": {
                "excluded_payment_types": [
                    {"id": "ticket"},
                    {"id": "atm"},
                ]
            }
        }

        result = sdk.preference().create(preference_data)
        preference = result.get("response", {})

        if "id" not in preference:
            logger.error(f"Error MP: {preference}")
            return False

        return {
            "id": preference["id"],
            "init_point": preference["init_point"],
            "monto_a_pagar": monto_a_pagar,
        }

    except Exception as e:
        logger.error(f"Excepción MP: {e}")
        return False


def procesar_pago_aprobado(compra_pendiente, payment_info: dict) -> bool:
    """
    Procesa un pago aprobado de Mercado Pago.
    Equivale a procesarPagoAprobado() de CI3 Webhook_model.
    """
    from apps.comedor.models import LogCarga

    with transaction.atomic():
        # Bloqueo pesimista
        compra = CompraPendiente.objects.select_for_update().get(
            id=compra_pendiente.id
        )

        if compra.procesada:
            logger.info(f"Compra {compra.id} ya procesada.")
            return True

        # Marcar como procesada inmediatamente
        compra.procesada = True
        compra.mp_estado = 'approved'
        compra.save(update_fields=['procesada', 'mp_estado'])

        usuario = compra.usuario
        total = float(compra.total)
        monto_pagado_mp = float(payment_info.get('transaction_amount', 0))
        saldo_actual = float(usuario.saldo)

        # Calcular saldo a deducir
        saldo_a_deducir = max(0, min(total - monto_pagado_mp, saldo_actual))
        saldo_final = saldo_actual - saldo_a_deducir

        # Crear transacción principal
        transaccion = Transaccion.objects.create(
            usuario=usuario,
            transaccion='Compra por Mercado Pago',
            monto=-total,
            saldo=saldo_final,
            external_reference=compra.external_reference,
        )

        # Vendedor MP
        try:
            from apps.accounts.models import CustomUser
            vendedor_mp = CustomUser.objects.get(email='mercado@pago')
        except CustomUser.DoesNotExist:
            vendedor_mp = None

        # Log de carga MP
        LogCarga.objects.create(
            usuario=usuario,
            vendedor=vendedor_mp,
            monto=monto_pagado_mp,
            formato='MP',
            transaccion=transaccion,
        )

        # Crear compras individuales
        viandas = json.loads(compra.datos)
        for vianda in viandas:
            Compra.objects.create(
                usuario=usuario,
                dia_comprado=vianda['dia_comprado'],
                precio=vianda['precio'],
                turno=vianda['turno'],
                menu=vianda['menu'],
                tipo=vianda.get('tipo', ''),
                transaccion=transaccion,
                external_reference=compra.external_reference,
            )
            LogCompra.objects.create(
                usuario=usuario,
                dia_comprado=vianda['dia_comprado'],
                precio=vianda['precio'],
                turno=vianda['turno'],
                menu=vianda['menu'],
                tipo=vianda.get('tipo', ''),
                transaccion_tipo='Compra por Mercado Pago',
                transaccion=transaccion,
                external_reference=compra.external_reference,
            )

        # Actualizar saldo
        if saldo_a_deducir > 0:
            usuario.saldo = saldo_final
            usuario.save(update_fields=['saldo'])

        # Eliminar compra pendiente
        compra.delete()

    return True


def procesar_pago_rechazado(compra_pendiente, payment_info: dict) -> bool:
    """
    Procesa un pago rechazado de Mercado Pago.
    Equivale a procesarPagoRechazado() de CI3 Webhook_model.
    """
    if compra_pendiente.procesada:
        return True

    compra_pendiente.mp_estado = 'rejected'
    compra_pendiente.save(update_fields=['mp_estado'])

    return True


def limpiar_compras_rechazadas(usuario) -> None:
    """Elimina compras pendientes rechazadas con más de 1 día."""
    from django.utils import timezone
    from datetime import timedelta

    CompraPendiente.objects.filter(
        usuario=usuario,
        mp_estado='rejected',
        procesada=False,
        created_at__lt=timezone.now() - timedelta(days=1)
    ).delete()
