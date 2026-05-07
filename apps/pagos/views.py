# apps/pagos/views.py
import json
import logging
import hmac
import hashlib

from django.shortcuts import render, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.views import View
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.conf import settings

from apps.comedor.services import es_fecha_vianda_ordenable, procesar_compra_con_saldo
from .models import CompraPendiente
from .services import (
    crear_compra_pendiente,
    generar_preferencia_mp,
    procesar_pago_aprobado,
    procesar_pago_rechazado,
    limpiar_compras_rechazadas,
)

logger = logging.getLogger(__name__)


class ProcesarCompraView(LoginRequiredMixin, View):
    """
    Equivale a comprar() de Pago.php en CI3.
    Recibe la selección de la sesión y decide si
    paga con saldo o redirige a MP.
    """

    def get(self, request):
        usuario = request.user
        seleccion_json = request.session.get('seleccion_compra')
        total = request.session.get('total_compra')

        if not seleccion_json or not total:
            return redirect('comedor:index')

        seleccion = json.loads(seleccion_json)

        # Verificar que no haya compra en pasarela activa
        compra_activa = CompraPendiente.get_pasarela_activa(usuario)
        if compra_activa:
            messages.error(
                request,
                'Tenés una compra pendiente de pago. Retomala o cancelala antes de continuar.'
            )
            return redirect('comedor:index')

        # Revalidar fechas
        for vianda in seleccion:
            if not es_fecha_vianda_ordenable(vianda['dia_comprado']):
                messages.error(
                    request,
                    'Algunas viandas ya no pueden comprarse. '
                    'Sus plazos expiraron. Iniciá una nueva compra.'
                )
                del request.session['seleccion_compra']
                del request.session['total_compra']
                return redirect('comedor:index')

        # Limpiar rechazadas anteriores
        limpiar_compras_rechazadas(usuario)

        # Crear compra pendiente
        compra_pendiente = crear_compra_pendiente(usuario, seleccion, total)
        compra_pendiente.mp_estado = 'pasarela'
        compra_pendiente.save(update_fields=['mp_estado'])

        # Limpiar sesión
        del request.session['seleccion_compra']
        del request.session['total_compra']

        # Guardar referencia en sesión
        request.session['external_reference'] = compra_pendiente.external_reference

        # Intentar pagar con saldo
        preferencia = generar_preferencia_mp(compra_pendiente, usuario)

        if preferencia is None:
            # Saldo cubre todo
            ok = procesar_compra_con_saldo(compra_pendiente, float(total))
            if ok:
                request.session['send_balance_email'] = True
                return redirect(
                    f"{settings.MP_BACK_URL_SUCCESS}"
                    f"?external_reference={compra_pendiente.external_reference}"
                )
            else:
                messages.error(
                    request, 'Error al procesar la compra con saldo.')
                return redirect('comedor:index')

        elif preferencia is False:
            messages.error(
                request, 'Error al generar el pago. Intentá nuevamente.')
            return redirect('comedor:index')

        else:
            # Redirigir a MP
            return redirect(preferencia['init_point'])


class CompraExitosaView(LoginRequiredMixin, View):

    template_name = 'pagos/exitoso.html'

    def get(self, request):
        external_reference = request.GET.get('external_reference')

        if not external_reference:
            return redirect('comedor:index')

        # Limpiar sesión
        request.session.pop('external_reference', None)
        request.session.pop('send_balance_email', None)

        return render(request, self.template_name, {
            'titulo': '¡Pago exitoso!'
        })


class CompraFallidaView(View):

    template_name = 'pagos/fallido.html'

    def get(self, request):
        request.session.pop('external_reference', None)
        return render(request, self.template_name, {
            'titulo': 'Pago fallido'
        })


class CompraPendienteView(View):

    template_name = 'pagos/pendiente.html'

    def get(self, request):
        external_reference = request.GET.get('external_reference')

        if external_reference:
            CompraPendiente.objects.filter(
                external_reference=external_reference
            ).update(mp_estado='pending')

        request.session.pop('external_reference', None)

        return render(request, self.template_name, {
            'titulo': 'Pago pendiente'
        })


class CancelarCompraAjaxView(LoginRequiredMixin, View):

    def post(self, request):
        external_reference = request.POST.get('external_reference')

        if not external_reference:
            return HttpResponse(
                json.dumps(
                    {'success': False, 'message': 'Referencia no proporcionada.'}),
                content_type='application/json'
            )

        try:
            compra = CompraPendiente.objects.get(
                external_reference=external_reference,
                usuario=request.user
            )
        except CompraPendiente.DoesNotExist:
            return HttpResponse(
                json.dumps(
                    {'success': False, 'message': 'Compra no encontrada.'}),
                content_type='application/json'
            )

        estados_no_cancelables = [
            'approved', 'rejected', 'cancelled', 'expired_by_date_cutoff']
        if compra.mp_estado in estados_no_cancelables:
            return HttpResponse(
                json.dumps({
                    'success': False,
                    'message': f'Esta compra no puede cancelarse. Estado: {compra.mp_estado}'
                }),
                content_type='application/json'
            )

        compra.mp_estado = 'cancelled_by_user'
        compra.save(update_fields=['mp_estado'])
        request.session.pop('external_reference', None)

        return HttpResponse(
            json.dumps({
                'success': True,
                'message': 'Compra cancelada. Podés iniciar una nueva selección.'
            }),
            content_type='application/json'
        )


@method_decorator(csrf_exempt, name='dispatch')
class WebhookMercadoPagoView(View):
    """
    Equivale a mercadopago() de Webhook.php en CI3.
    """

    def post(self, request):
        # Validar firma HMAC
        if not self._validar_firma(request):
            logger.warning("Webhook MP: firma inválida.")
            return HttpResponse(status=401)

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            logger.error("Webhook MP: JSON inválido.")
            return HttpResponse(status=400)

        if not isinstance(data, dict) or not data:
            return HttpResponse(status=400)

        tipo = data.get('type')
        payment_id = data.get('data', {}).get('id')

        if tipo != 'payment' or not payment_id:
            logger.info(f"Webhook MP: tipo no manejado: {tipo}")
            return HttpResponse(status=200)

        try:
            import mercadopago
            sdk = mercadopago.SDK(settings.MP_ACCESS_TOKEN)
            result = sdk.payment().get(payment_id)
            payment_info = result.get('response', {})

            if not payment_info:
                logger.error(
                    f"Webhook MP: no se pudo obtener pago {payment_id}")
                return HttpResponse(status=200)

            external_reference = payment_info.get('external_reference')
            mp_status = payment_info.get('status')

            try:
                compra = CompraPendiente.objects.get(
                    external_reference=external_reference
                )
            except CompraPendiente.DoesNotExist:
                logger.warning(
                    f"Webhook MP: compra no encontrada {external_reference}")
                return HttpResponse(status=200)

            # Actualizar estado
            compra.mp_estado = mp_status
            compra.save(update_fields=['mp_estado'])

            if mp_status == 'approved':
                procesar_pago_aprobado(compra, payment_info)
                self._enviar_email_compra(compra, payment_info)

            elif mp_status in ['rejected', 'cancelled']:
                procesar_pago_rechazado(compra, payment_info)
                self._enviar_email_rechazo(compra, payment_info)

            else:
                logger.info(
                    f"Webhook MP: estado {mp_status} para {external_reference}")

        except Exception as e:
            logger.error(f"Webhook MP: excepción {e}")
            return HttpResponse(status=500)

        return HttpResponse(status=200)

    def _validar_firma(self, request) -> bool:
        secret = settings.MP_WEBHOOK_SECRET
        if not secret:
            return True  # Sin secret configurado no validamos en desarrollo

        x_signature = request.headers.get('x-signature', '')
        x_request_id = request.headers.get('x-request-id', '')

        ts = None
        v1 = None
        for part in x_signature.split(','):
            kv = part.strip().split('=', 1)
            if len(kv) == 2:
                if kv[0] == 'ts':
                    ts = kv[1]
                elif kv[0] == 'v1':
                    v1 = kv[1]

        if not ts or not v1:
            return False

        try:
            data = json.loads(request.body)
            data_id = data.get('data', {}).get('id', '')
        except Exception:
            return False

        manifest = f"id:{data_id};"
        if x_request_id:
            manifest += f"request-id:{x_request_id};"
        manifest += f"ts:{ts};"

        calculated = hmac.new(
            secret.encode(),
            manifest.encode(),
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(calculated, v1)

    def _enviar_email_compra(self, compra, payment_info):
        from django.core.mail import send_mail
        from django.template.loader import render_to_string

        usuario = compra.usuario
        try:
            from apps.comedor.models import Transaccion
            transaccion = Transaccion.objects.filter(
                external_reference=compra.external_reference
            ).first()

            context = {
                'user_name': usuario.nombre_completo,
                'compras': transaccion.compras.all() if transaccion else [],
                'total': abs(transaccion.monto) if transaccion else compra.total,
                'recibo_numero': compra.external_reference,
            }
            mensaje = render_to_string('emails/recibo_compra.html', context)
            send_mail(
                subject='Confirmación de Compra - Comedor UTN FRLP',
                message='',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[usuario.email],
                html_message=mensaje,
                fail_silently=True,
            )
        except Exception as e:
            logger.error(f"Error enviando email compra: {e}")

    def _enviar_email_rechazo(self, compra, payment_info):
        from django.core.mail import send_mail
        from django.template.loader import render_to_string
        import json

        usuario = compra.usuario
        try:
            viandas = json.loads(compra.datos)
            context = {
                'user_name': usuario.nombre_completo,
                'external_reference': compra.external_reference,
                'status_detail': payment_info.get('status_detail', ''),
                'viandas': viandas,
            }
            mensaje = render_to_string('emails/pago_rechazado.html', context)
            send_mail(
                subject='Pago Rechazado - Comedor UTN FRLP',
                message='',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[usuario.email],
                html_message=mensaje,
                fail_silently=True,
            )
        except Exception as e:
            logger.error(f"Error enviando email rechazo: {e}")
