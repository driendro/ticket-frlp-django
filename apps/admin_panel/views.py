# apps/admin_panel/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.views import View
from django.db import transaction
from django.core.paginator import Paginator

from apps.accounts.models import CustomUser
from apps.core.models import Precio
from apps.comedor.models import Transaccion, LogCarga, Compra
from apps.pagos.models import CargaVirtual
from .mixins import CajeroRequiredMixin, AdministradorRequiredMixin, RepartidorRequiredMixin


class IndexView(CajeroRequiredMixin, View):
    """
    Panel principal del vendedor.
    Equivale a index() de Vendedor.php en CI3.
    """
    template_name = 'admin_panel/index.html'

    def get(self, request):
        usuario = None
        documento = request.GET.get('documento')

        if documento:
            try:
                usuario = CustomUser.objects.get(documento=int(documento))
            except (CustomUser.DoesNotExist, ValueError):
                messages.error(
                    request, 'No existe un usuario con ese documento.')

        context = {
            'titulo': 'Carga de Saldo',
            'usuario': usuario,
        }
        return render(request, self.template_name, context)

    def post(self, request):
        documento = request.POST.get('numeroDni')
        try:
            usuario = CustomUser.objects.get(documento=int(documento))
            return render(request, self.template_name, {
                'titulo': 'Carga de Saldo',
                'usuario': usuario,
            })
        except (CustomUser.DoesNotExist, ValueError):
            messages.error(request, 'No existe un usuario con ese documento.')
            return redirect('admin_panel:index')


class CargarSaldoView(CajeroRequiredMixin, View):
    """
    Equivale a cargarSaldo() de Vendedor.php en CI3.
    """

    def post(self, request):
        documento = request.POST.get('dni')
        monto = request.POST.get('carga')
        metodo = request.POST.get('metodo_carga')

        if not documento or not monto or not metodo:
            messages.error(request, 'Completá todos los campos.')
            return redirect('admin_panel:index')

        try:
            monto = float(monto)
            if monto == 0:
                messages.error(request, 'El monto debe ser distinto de 0.')
                return redirect('admin_panel:index')
        except ValueError:
            messages.error(request, 'El monto debe ser numérico.')
            return redirect('admin_panel:index')

        try:
            usuario = CustomUser.objects.get(documento=int(documento))
        except CustomUser.DoesNotExist:
            messages.error(request, 'Usuario no encontrado.')
            return redirect('admin_panel:index')

        with transaction.atomic():
            nuevo_saldo = float(usuario.saldo) + monto
            tipo = 'Carga de Saldo' if monto > 0 else 'Devolucion de Saldo'

            transaccion = Transaccion.objects.create(
                usuario=usuario,
                transaccion=tipo,
                monto=monto,
                saldo=nuevo_saldo,
            )

            LogCarga.objects.create(
                usuario=usuario,
                vendedor=request.user,
                monto=monto,
                formato=metodo,
                transaccion=transaccion,
            )

            usuario.saldo = nuevo_saldo
            usuario.save(update_fields=['saldo'])

        # Enviar email
        self._enviar_email_carga(usuario, transaccion,
                                 metodo, monto, nuevo_saldo)

        messages.success(
            request,
            f'Se cargaron ${monto} a {usuario.nombre_completo}. '
            f'Nuevo saldo: ${nuevo_saldo}'
        )
        return redirect('admin_panel:index')

    def _enviar_email_carga(self, usuario, transaccion, metodo, monto, saldo):
        from django.core.mail import send_mail
        from django.template.loader import render_to_string
        from django.conf import settings

        try:
            context = {
                'transaccion': transaccion.id,
                'usuario': usuario,
                'monto': monto,
                'saldo': saldo,
                'metodo': metodo,
            }
            mensaje = render_to_string('emails/carga_saldo.html', context)
            send_mail(
                subject='Carga de Saldo - Comedor UTN FRLP',
                message='',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[usuario.email],
                html_message=mensaje,
                fail_silently=True,
            )
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Error email carga: {e}")


class CrearUsuarioView(CajeroRequiredMixin, View):
    """
    Equivale a createUser() de Vendedor.php en CI3.
    """
    template_name = 'admin_panel/crear_usuario.html'

    def get(self, request):
        precios = Precio.objects.all()
        return render(request, self.template_name, {
            'titulo': 'Nuevo Usuario',
            'precios': precios,
        })

    def post(self, request):
        datos = {
            'documento': request.POST.get('dni'),
            'legajo': request.POST.get('legajo'),
            'first_name': request.POST.get('nombre', '').title(),
            'last_name': request.POST.get('apellido', '').title(),
            'email': request.POST.get('email', '').lower(),
            'tipo': request.POST.get('claustro'),
            'especialidad': request.POST.get('especialidad') or None,
            'es_becado': request.POST.get('beca') == 'Si',
            'saldo': float(request.POST.get('saldo', 0)),
        }

        # Validaciones básicas
        errores = []
        if CustomUser.objects.filter(documento=datos['documento']).exists():
            errores.append('Ese documento ya está registrado.')
        if CustomUser.objects.filter(legajo=datos['legajo']).exists():
            errores.append('Ese legajo ya está registrado.')
        if CustomUser.objects.filter(email=datos['email']).exists():
            errores.append('Ese email ya está registrado.')

        if errores:
            for e in errores:
                messages.error(request, e)
            return render(request, self.template_name, {
                'titulo': 'Nuevo Usuario',
                'precios': Precio.objects.all(),
            })

        # Generar password aleatorio
        import random
        import string
        letras = ''.join(random.choices(string.ascii_lowercase, k=3))
        numeros = ''.join(random.choices(string.digits, k=3))
        password = f"{letras}{numeros}"

        with transaction.atomic():
            usuario = CustomUser.objects.create_user(
                username=str(datos['documento']),
                documento=datos['documento'],
                password=password,
                **{k: v for k, v in datos.items()
                   if k not in ['documento']},
            )

            # Log de alta
            from apps.comedor.models import LogCarga
            if datos['saldo'] > 0:
                transaccion = Transaccion.objects.create(
                    usuario=usuario,
                    transaccion='Carga de Saldo',
                    monto=datos['saldo'],
                    saldo=datos['saldo'],
                )
                LogCarga.objects.create(
                    usuario=usuario,
                    vendedor=request.user,
                    monto=datos['saldo'],
                    formato='Efectivo',
                    transaccion=transaccion,
                )

        # Email bienvenida
        self._enviar_email_bienvenida(usuario, password)

        messages.success(
            request, f'Usuario {usuario.nombre_completo} creado correctamente.')
        return redirect('admin_panel:index')

    def _enviar_email_bienvenida(self, usuario, password):
        from django.core.mail import send_mail
        from django.template.loader import render_to_string
        from django.conf import settings

        try:
            context = {'usuario': usuario, 'password': password}
            mensaje = render_to_string('emails/nuevo_usuario.html', context)
            send_mail(
                subject='Bienvenido al Comedor UTN FRLP',
                message='',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[usuario.email],
                html_message=mensaje,
                fail_silently=True,
            )
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Error email bienvenida: {e}")


class ModificarUsuarioView(CajeroRequiredMixin, View):
    """
    Equivale a updateUser() de Vendedor.php en CI3.
    """
    template_name = 'admin_panel/modificar_usuario.html'

    def get(self, request, pk):
        usuario = get_object_or_404(CustomUser, pk=pk)
        return render(request, self.template_name, {
            'titulo': f'Modificar {usuario.nombre_completo}',
            'usuario': usuario,
        })

    def post(self, request, pk):
        usuario = get_object_or_404(CustomUser, pk=pk)

        usuario.first_name = request.POST.get('nombre', '').title()
        usuario.last_name = request.POST.get('apellido', '').title()
        usuario.email = request.POST.get('email', '').lower()
        usuario.tipo = request.POST.get('claustro')
        usuario.especialidad = request.POST.get('especialidad') or None
        usuario.es_becado = request.POST.get('beca') == 'Si'
        usuario.legajo = request.POST.get('legajo')
        usuario.documento = request.POST.get('documento')
        usuario.save()

        messages.success(request, 'Usuario actualizado correctamente.')
        return redirect('admin_panel:index')


class HistorialCargasView(CajeroRequiredMixin, View):
    """
    Equivale a historialCargas() de Vendedor.php en CI3.
    """
    template_name = 'admin_panel/historial_cargas.html'

    def get(self, request):
        cargas = LogCarga.objects.filter(
            vendedor=request.user
        ).select_related('usuario').order_by('-fecha', '-hora')[:20]

        return render(request, self.template_name, {
            'titulo': 'Historial de Cargas',
            'cargas': cargas,
        })


class VerComprasUsuarioView(AdministradorRequiredMixin, View):
    """
    Equivale a ver_compras_userid() de Administrador.php en CI3.
    """
    template_name = 'admin_panel/ver_compras.html'

    def get(self, request, pk):
        usuario = get_object_or_404(CustomUser, pk=pk)
        compras_qs = Compra.objects.filter(
            usuario=usuario
        ).select_related('transaccion').order_by('-dia_comprado')

        paginator = Paginator(compras_qs, 10)
        page = request.GET.get('page', 1)
        compras = paginator.get_page(page)

        return render(request, self.template_name, {
            'titulo': f'Compras de {usuario.nombre_completo}',
            'usuario': usuario,
            'compras': compras,
        })


class DevolverCompraAdminView(AdministradorRequiredMixin, View):
    """
    Equivale a devolver_compra_by_id() de Administrador.php en CI3.
    """

    def get(self, request, usuario_pk, compra_pk):
        usuario = get_object_or_404(CustomUser, pk=usuario_pk)
        compra = get_object_or_404(Compra, pk=compra_pk, usuario=usuario)

        with transaction.atomic():
            nuevo_saldo = float(usuario.saldo) + float(compra.precio)

            transaccion = Transaccion.objects.create(
                usuario=usuario,
                transaccion='Reintegro',
                monto=compra.precio,
                saldo=nuevo_saldo,
            )

            from apps.comedor.models import LogCompra
            LogCompra.objects.create(
                usuario=usuario,
                dia_comprado=compra.dia_comprado,
                precio=compra.precio,
                turno=compra.turno,
                menu=compra.menu,
                tipo=compra.tipo,
                transaccion_tipo='Reintegro',
                transaccion=transaccion,
            )

            usuario.saldo = nuevo_saldo
            usuario.save(update_fields=['saldo'])
            compra.delete()

        messages.success(
            request,
            f'Se reintegró ${compra.precio} a {usuario.nombre_completo}.'
        )
        return redirect('admin_panel:ver_compras', pk=usuario_pk)


class RepartidorView(RepartidorRequiredMixin, View):
    """
    Equivale a buscar_compra_por_fecha_user() de Repartidor.php en CI3.
    """
    template_name = 'admin_panel/repartidor.html'

    def get(self, request):
        return render(request, self.template_name, {
            'titulo': 'Entrega de Viandas',
        })

    def post(self, request):
        from datetime import date
        documento = request.POST.get('numeroDni')
        hoy = date.today()

        try:
            usuario = CustomUser.objects.get(documento=int(documento))
            compra = Compra.objects.filter(
                usuario=usuario,
                dia_comprado=hoy
            ).first()
        except (CustomUser.DoesNotExist, ValueError):
            usuario = None
            compra = None

        return render(request, self.template_name, {
            'titulo': 'Entrega de Viandas',
            'usuario': usuario,
            'compra': compra,
        })


class EntregarViandaView(RepartidorRequiredMixin, View):
    """
    Equivale a entregar_compra_by_id() de Repartidor.php en CI3.
    """

    def post(self, request):
        compra_id = request.POST.get('idCompra')
        compra = get_object_or_404(Compra, pk=compra_id)

        compra.retiro = True
        compra.repartidor = request.user
        compra.save(update_fields=['retiro', 'repartidor'])

        messages.success(request, 'Vianda entregada correctamente.')
        return redirect('admin_panel:repartidor')
