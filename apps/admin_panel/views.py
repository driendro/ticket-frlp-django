# apps/admin_panel/views.py
from datetime import datetime, date, timedelta
from collections import defaultdict
from statistics import mean, median
from django.db.models import Sum, Count
from django.http import HttpResponse
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
from openpyxl.cell import MergedCell
import openpyxl
import io
import csv
from apps.core.models import Configuracion, Feriado, Menu
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.views import View
from django.db import transaction
from django.core.paginator import Paginator

from apps.accounts.models import CustomUser
from apps.core.models import Precio
from apps.comedor.models import Transaccion, LogCarga, Compra
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
            'especialidad_choices': CustomUser.ESPECIALIDAD_CHOICES,
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

        from django.utils import timezone
        compra.retiro = True
        compra.repartidor = request.user
        compra.hora_retiro = timezone.localtime().time()
        compra.save(update_fields=['retiro', 'repartidor', 'hora_retiro'])

        messages.success(request, 'Vianda entregada correctamente.')
        return redirect('admin_panel:repartidor')


# apps/admin_panel/views.py - agregar al final del archivo existente


class ConfiguracionView(AdministradorRequiredMixin, View):
    """
    Equivale a configuracion_general() de Administrador.php en CI3.
    """
    template_name = 'admin_panel/configuracion.html'


    def get(self, request):
        config = Configuracion.get()
        dias_semana = {
            1: 'Lunes', 2: 'Martes', 3: 'Miércoles',
            4: 'Jueves', 5: 'Viernes', 6: 'Sábado', 7: 'Domingo'
        }
        return render(request, self.template_name, {
            'titulo': 'Configuración General',
            'config': config,
            'dias_semana': dias_semana,
        })

    def post(self, request):
        config = Configuracion.get()

        if not config:
            config = Configuracion()

        config.apertura = request.POST.get('apertura_comedor')
        config.cierre = request.POST.get('cierre_comedor')
        config.vacaciones_inicio = request.POST.get('inicio_receso')
        config.vacaciones_fin = request.POST.get('fin_receso')
        config.dia_inicial = int(request.POST.get('inicio_venta_semana'))
        config.dia_final = int(request.POST.get('fin_venta_semana'))
        config.hora_final = request.POST.get('hora_cierre_venta')
        config.permitir_ambos_turnos = request.POST.get(
            'permitir_ambos_turnos') == 'on'
        config.save()

        messages.success(request, 'Configuración guardada correctamente.')
        return redirect('admin_panel:configuracion')


class PreciosView(AdministradorRequiredMixin, View):
    """
    Equivale a configuracion_costos() de Administrador.php en CI3.
    """
    template_name = 'admin_panel/precios.html'

    def get(self, request):
        precios = Precio.objects.all()
        return render(request, self.template_name, {
            'titulo': 'Configuración de Precios',
            'precios': precios,
        })

    def post(self, request):
        precios = Precio.objects.all()
        for precio in precios:
            costo = request.POST.get(f'precio_{precio.id}')
            if costo:
                precio.costo = float(costo)
                precio.save(update_fields=['costo'])

        messages.success(request, 'Precios actualizados correctamente.')
        return redirect('admin_panel:precios')


class FeriadosView(AdministradorRequiredMixin, View):
    """
    Equivale a feriados_list() de Administrador.php en CI3.
    """
    template_name = 'admin_panel/feriados.html'

    def get(self, request):
        from datetime import date
        año = int(request.GET.get('año', date.today().year))
        feriados = Feriado.objects.filter(
            fecha__year=año
        ).order_by('fecha')

        return render(request, self.template_name, {
            'titulo': 'Feriados',
            'feriados': feriados,
            'año': año,
        })


def _devolver_compras_fecha(fecha, motivo):
    from apps.comedor.models import LogCompra
    from django.core.mail import send_mail
    from django.template.loader import render_to_string
    from django.conf import settings
    import logging

    for compra in Compra.objects.filter(dia_comprado=fecha):
        usuario = compra.usuario
        nuevo_saldo = float(usuario.saldo) + float(compra.precio)

        transaccion = Transaccion.objects.create(
            usuario=usuario,
            transaccion='Reintegro',
            monto=compra.precio,
            saldo=nuevo_saldo,
        )
        LogCompra.objects.create(
            usuario=usuario,
            dia_comprado=compra.dia_comprado,
            precio=compra.precio,
            turno=compra.turno,
            menu=compra.menu,
            transaccion_tipo='Reintegro',
            transaccion=transaccion,
        )
        usuario.saldo = nuevo_saldo
        usuario.save(update_fields=['saldo'])
        compra.delete()

        try:
            mensaje = render_to_string('emails/reintegro.html', {
                'usuario': usuario,
                'compra': compra,
                'motivo': motivo,
                'saldo': nuevo_saldo,
            })
            send_mail(
                subject=f'Reintegro por {motivo}',
                message='',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[usuario.email],
                html_message=mensaje,
                fail_silently=True,
            )
        except Exception as e:
            logging.getLogger(__name__).error(f"Error email reintegro: {e}")


class AgregarFeriadoView(AdministradorRequiredMixin, View):
    """
    Equivale a add_feriado() de Administrador.php en CI3.
    """

    def post(self, request):
        fecha = request.POST.get('fecha_feriado')
        detalle = request.POST.get('fecha_feriado_motivo')
        año = request.POST.get('ano')

        if fecha and detalle:
            feriado, creado = Feriado.objects.get_or_create(
                fecha=fecha,
                defaults={'detalle': detalle}
            )
            if creado:
                _devolver_compras_fecha(fecha, detalle)
                messages.success(request, f'Feriado {fecha} agregado.')
            else:
                messages.warning(request, 'Ya existe un feriado para esa fecha.')

        return redirect(f"{request.build_absolute_uri('?')}año={año}" if año
                        else 'admin_panel:feriados')


class EliminarFeriadoView(AdministradorRequiredMixin, View):
    """
    Equivale a borrar_feriado() de Administrador.php en CI3.
    """

    def get(self, request, pk):
        feriado = get_object_or_404(Feriado, pk=pk)
        año = feriado.fecha.year
        feriado.delete()
        messages.success(request, 'Feriado eliminado.')
        return redirect(f"{request.build_absolute_uri('/panel/feriados/')}?año={año}")


class ImportarFeriadosCSVView(AdministradorRequiredMixin, View):

    FORMATOS_FECHA = ['%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y']

    def post(self, request):
        archivo = request.FILES.get('csv_feriados')
        if not archivo:
            messages.error(request, 'Seleccioná un archivo CSV.')
            return redirect('admin_panel:feriados')

        try:
            contenido = archivo.read().decode('utf-8-sig')
            reader = csv.reader(io.StringIO(contenido))
        except Exception:
            messages.error(request, 'No se pudo leer el archivo.')
            return redirect('admin_panel:feriados')

        agregados, omitidos, errores = 0, 0, []

        for num, fila in enumerate(reader, start=1):
            if not fila or all(c.strip() == '' for c in fila):
                continue

            fecha_str = fila[0].strip()
            motivo = fila[1].strip() if len(fila) > 1 else ''

            fecha = None
            for fmt in self.FORMATOS_FECHA:
                try:
                    from datetime import datetime as dt
                    fecha = dt.strptime(fecha_str, fmt).date()
                    break
                except ValueError:
                    pass

            if fecha is None:
                # Puede ser la fila de cabecera — la saltamos en silencio si es la primera
                if num == 1:
                    continue
                errores.append(f'Fila {num}: fecha "{fecha_str}" no reconocida.')
                continue

            if not motivo:
                errores.append(f'Fila {num}: falta el motivo.')
                continue

            _, creado = Feriado.objects.get_or_create(
                fecha=fecha,
                defaults={'detalle': motivo}
            )
            if creado:
                _devolver_compras_fecha(fecha, motivo)
                agregados += 1
            else:
                omitidos += 1

        if agregados:
            messages.success(request, f'{agregados} feriado(s) importado(s) correctamente.')
        if omitidos:
            messages.warning(request, f'{omitidos} feriado(s) ya existían y fueron omitidos.')
        for e in errores:
            messages.error(request, e)

        return redirect('admin_panel:feriados')


class MenuAdminView(AdministradorRequiredMixin, View):
    """
    Equivale a updateMenu() de Vendedor.php en CI3.
    """
    template_name = 'admin_panel/menu.html'

    def get(self, request):
        menu = Menu.objects.all().order_by('dia')
        return render(request, self.template_name, {
            'titulo': 'Actualizar Menú',
            'menu': menu,
        })

    def post(self, request):
        menu = Menu.objects.all().order_by('dia')
        for item in menu:
            item.menu_basico = request.POST.get(f'basico_{item.id}', '')
            item.menu_veggie = request.POST.get(f'veggie_{item.id}', '')
            item.menu_sin_tacc = request.POST.get(f'sin_tacc_{item.id}', '')
            item.save()

        messages.success(request, 'Menú actualizado correctamente.')
        return redirect('admin_panel:menu')


class CargaCSVView(AdministradorRequiredMixin, View):
    """
    Equivale a cargar_archivo_csv() de Administrador.php en CI3.
    """
    template_name = 'admin_panel/carga_csv.html'

    def get(self, request):
        return render(request, self.template_name, {
            'titulo': 'Carga CSV',
        })

    def post(self, request):
        archivo = request.FILES.get('archivo_csv')
        separador = request.POST.get('separador', ';')

        if not archivo:
            messages.error(request, 'Seleccioná un archivo CSV.')
            return redirect('admin_panel:carga_csv')

        try:
            contenido = archivo.read().decode('utf-8')
            reader = csv.reader(io.StringIO(contenido), delimiter=separador)
            next(reader)  # saltar header
            cargas = list(reader)
        except Exception as e:
            messages.error(request, f'Error al leer el archivo: {e}')
            return redirect('admin_panel:carga_csv')

        return render(request, self.template_name, {
            'titulo': 'Carga CSV',
            'cargas': cargas,
            'separador': separador,
        })


class ConfirmarCSVView(AdministradorRequiredMixin, View):
    """
    Equivale a confirmarCargasCVS() de Administrador.php en CI3.
    """

    def post(self, request):
        errores = []
        i = 0

        while request.POST.get(f'documento_{i}'):
            documento = request.POST.get(f'documento_{i}')
            monto = float(request.POST.get(f'monto_{i}', 0))
            tipo = request.POST.get(f'tipo_{i}', 'Efectivo')

            try:
                usuario = CustomUser.objects.get(documento=int(documento))
                nuevo_saldo = float(usuario.saldo) + monto
                tipo_trans = 'Carga de Saldo' if monto >= 0 else 'Devolucion de Saldo'

                with transaction.atomic():
                    transaccion = Transaccion.objects.create(
                        usuario=usuario,
                        transaccion=tipo_trans,
                        monto=monto,
                        saldo=nuevo_saldo,
                    )
                    LogCarga.objects.create(
                        usuario=usuario,
                        vendedor=request.user,
                        monto=monto,
                        formato=tipo,
                        transaccion=transaccion,
                    )
                    usuario.saldo = nuevo_saldo
                    usuario.save(update_fields=['saldo'])

            except CustomUser.DoesNotExist:
                errores.append(documento)

            i += 1

        if errores:
            messages.warning(
                request,
                f'No se encontraron los documentos: {", ".join(errores)}'
            )
        else:
            messages.success(request, 'Cargas realizadas correctamente.')

        return redirect('admin_panel:carga_csv')


# apps/admin_panel/views.py - agregar al final


class DescargarExcelView(CajeroRequiredMixin, View):
    """
    Equivale a descargarExcel() de Vendedor.php en CI3.
    """

    def _semanas(self):
        """Retorna lista de 3 semanas (lun–vie): hace 2 semanas, la anterior y la actual."""
        from datetime import date, timedelta
        hoy = date.today()
        lunes_actual = hoy - timedelta(days=hoy.weekday())
        semanas = []
        for offset in range(2, -1, -1):
            lunes = lunes_actual - timedelta(weeks=offset)
            dias = [lunes + timedelta(days=i) for i in range(5)]
            semanas.append(dias)
        return semanas

    def get(self, request):
        return render(request, 'admin_panel/descarga_planilla.html', {
            'titulo': 'Descargar Listados',
            'semanas': self._semanas(),
        })

    def post(self, request):
        fechas_str = request.POST.getlist('fechas')
        fecha_especifica = request.POST.get('fecha_especifica', '').strip()

        if fecha_especifica:
            fechas_str.append(fecha_especifica)

        fechas = []
        for f in fechas_str:
            try:
                fechas.append(datetime.strptime(f, '%Y-%m-%d').date())
            except (ValueError, TypeError):
                pass

        fechas = sorted(set(fechas))

        if not fechas:
            messages.error(request, 'Seleccioná al menos una fecha.')
            return render(request, 'admin_panel/descarga_planilla.html', {
                'titulo': 'Descargar Listados',
                'semanas': self._semanas(),
            })

        header_fill = PatternFill(start_color='366092', end_color='366092', fill_type='solid')
        header_font = Font(color='FFFFFF', bold=True)
        headers = ['#', 'Documento', 'Apellido', 'Nombre', 'Menú', 'Turno', 'Claustro']

        wb = openpyxl.Workbook()
        wb.remove(wb.active)

        for fecha in fechas:
            compras = Compra.objects.filter(
                dia_comprado=fecha
            ).select_related('usuario').order_by('usuario__last_name')

            dias_es = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']
            meses_es = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic']
            nombre_hoja = f"{dias_es[fecha.weekday()]}-{fecha.day:02d}-{meses_es[fecha.month - 1]}"
            ws = wb.create_sheet(title=nombre_hoja)

            ws.merge_cells('A1:G1')
            ws['A1'] = f'Listado de viandas - {fecha.strftime("%d/%m/%Y")}'
            ws['A1'].font = Font(bold=True, size=14)
            ws['A1'].alignment = Alignment(horizontal='center')

            for col, header in enumerate(headers, 1):
                cell = ws.cell(row=2, column=col, value=header)
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(horizontal='center')

            if compras:
                for i, compra in enumerate(compras, 1):
                    ws.append([
                        i,
                        compra.usuario.documento,
                        compra.usuario.last_name.upper(),
                        compra.usuario.first_name,
                        compra.get_menu_display(),
                        compra.get_turno_display(),
                        compra.usuario.tipo,
                    ])
            else:
                ws.merge_cells('A3:G3')
                ws['A3'] = 'Sin compras para esta fecha.'
                ws['A3'].alignment = Alignment(horizontal='center')

            for i, col in enumerate(ws.columns, 1):
                max_length = max(
                    len(str(cell.value or ''))
                    for cell in col
                    if not isinstance(cell, MergedCell)
                ) or 10
                ws.column_dimensions[get_column_letter(i)].width = max_length + 4

        nombre = f'Listado_{fechas[0]}' if len(fechas) == 1 else f'Listado_{fechas[0]}_{fechas[-1]}'
        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="{nombre}.xlsx"'
        wb.save(response)
        return response


class CierreCajaDiarioView(CajeroRequiredMixin, View):
    """
    Equivale a descargarCierreCajaDiario() de Vendedor.php en CI3.
    """

    def get(self, request):
        return render(request, 'admin_panel/descarga_informe.html', {
            'titulo': 'Informes',
        })

    def post(self, request):
        from weasyprint import HTML
        from django.template.loader import render_to_string

        fecha_str = request.POST.get('cierre_fecha')
        try:
            fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            messages.error(request, 'Fecha inválida.')
            return redirect('admin_panel:informe')

        cargas = LogCarga.objects.filter(
            fecha=fecha
        ).select_related('usuario', 'vendedor', 'transaccion')

        # Totales por formato
        totales = {
            'Efectivo': {'cantidad': 0, 'total': 0},
            'Virtual': {'cantidad': 0, 'total': 0},
            'MP': {'cantidad': 0, 'total': 0},
        }

        for carga in cargas:
            formato = carga.formato
            if formato in totales:
                totales[formato]['cantidad'] += 1
                totales[formato]['total'] += float(abs(carga.monto))

        context = {
            'cargas': cargas,
            'totales': totales,
            'vendedor': request.user,
            'fecha': fecha.strftime('%d-%m-%Y'),
        }

        html_string = render_to_string(
            'admin_panel/pdf/caja_diaria.html', context)
        html = HTML(string=html_string)
        pdf = html.write_pdf()

        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="Cierre_{fecha}.pdf"'
        response.write(pdf)
        return response


class CierreCajaSemanalView(CajeroRequiredMixin, View):
    """
    Equivale a descargarCierreCajaSemana() de Vendedor.php en CI3.
    """

    def post(self, request):
        from weasyprint import HTML
        from django.template.loader import render_to_string

        fecha1_str = request.POST.get('cierre_fecha_1')
        fecha2_str = request.POST.get('cierre_fecha_2')

        try:
            fecha1 = datetime.strptime(fecha1_str, '%Y-%m-%d').date()
            fecha2 = datetime.strptime(fecha2_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            messages.error(request, 'Fechas inválidas.')
            return redirect('admin_panel:informe')

        cargas = LogCarga.objects.filter(
            fecha__gte=fecha1,
            fecha__lte=fecha2,
        )

        # Armar detalle por día
        detalle = []
        fecha_actual = fecha1
        while fecha_actual <= fecha2:
            cargas_dia = cargas.filter(fecha=fecha_actual)
            dia = {
                'fecha': fecha_actual,
                'efectivo_cantidad': 0,
                'efectivo_total': 0,
                'virtual_cantidad': 0,
                'virtual_total': 0,
                'mp_cantidad': 0,
                'mp_total': 0,
            }
            for carga in cargas_dia:
                monto = float(abs(carga.monto))
                if carga.formato == 'Efectivo':
                    dia['efectivo_cantidad'] += 1
                    dia['efectivo_total'] += monto
                elif carga.formato == 'Virtual':
                    dia['virtual_cantidad'] += 1
                    dia['virtual_total'] += monto
                elif carga.formato == 'MP':
                    dia['mp_cantidad'] += 1
                    dia['mp_total'] += monto
            detalle.append(dia)
            fecha_actual += timedelta(days=1)

        context = {
            'detalle': detalle,
            'vendedor': request.user,
            'fecha1': fecha1.strftime('%d-%m-%Y'),
            'fecha2': fecha2.strftime('%d-%m-%Y'),
            'total_efectivo': sum(d['efectivo_total'] for d in detalle),
            'total_virtual': sum(d['virtual_total'] for d in detalle),
            'total_mp': sum(d['mp_total'] for d in detalle),
        }

        html_string = render_to_string(
            'admin_panel/pdf/caja_semanal.html', context)
        html = HTML(string=html_string)
        pdf = html.write_pdf()

        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="Cierre_{fecha1}_{fecha2}.pdf"'
        response.write(pdf)
        return response


class ResumenPedidosSemanaView(CajeroRequiredMixin, View):
    """
    Equivale a descargarResumenPedidosSemana() de Vendedor.php en CI3.
    """

    def post(self, request):
        from weasyprint import HTML
        from django.template.loader import render_to_string

        fecha1_str = request.POST.get('semana_fecha_1')
        fecha2_str = request.POST.get('semana_fecha_2')

        try:
            fecha1 = datetime.strptime(fecha1_str, '%Y-%m-%d').date()
            fecha2 = datetime.strptime(fecha2_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            messages.error(request, 'Fechas inválidas.')
            return redirect('admin_panel:informe')

        compras = Compra.objects.filter(
            dia_comprado__gte=fecha1,
            dia_comprado__lte=fecha2,
        )

        detalle = []
        fecha_actual = fecha1
        while fecha_actual <= fecha2:
            compras_dia = compras.filter(dia_comprado=fecha_actual)
            dia = {
                'fecha': fecha_actual,
                'basico': compras_dia.filter(menu='Basico').count(),
                'veggie': compras_dia.filter(menu='Veggie').count(),
                'celiaco': compras_dia.filter(menu='Celiaco').count(),
            }
            detalle.append(dia)
            fecha_actual += timedelta(days=1)

        context = {
            'detalle': detalle,
            'fecha1': fecha1.strftime('%d-%m-%Y'),
            'fecha2': fecha2.strftime('%d-%m-%Y'),
        }

        html_string = render_to_string(
            'admin_panel/pdf/resumen_semanal.html', context)
        html = HTML(string=html_string)
        pdf = html.write_pdf()

        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="Pedidos_{fecha1}_{fecha2}.pdf"'
        response.write(pdf)
        return response


def _dashboard_data(fecha, vista):
    import json
    from apps.core.models import Comentario

    DIAS = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes']
    DIAS_CORTO = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie']

    # ── Fecha seleccionada ─────────────────────────────────────────────────
    qs_fecha = Compra.objects.filter(dia_comprado=fecha)
    compras_dia   = qs_fecha.count()
    entregas_dia  = qs_fecha.filter(retiro=True).count()

    por_menu  = [qs_fecha.filter(menu=m).count() for m in ('Basico', 'Veggie', 'Celiaco')]
    por_turno = [qs_fecha.filter(turno=t).count() for t in ('manana', 'noche')]

    cargas_metodo = {'Efectivo': 0, 'Virtual': 0, 'MP': 0}
    for c in LogCarga.objects.filter(fecha=fecha):
        if c.formato in cargas_metodo and c.monto > 0:
            cargas_metodo[c.formato] += float(c.monto)

    # ── Sistema ────────────────────────────────────────────────────────────
    saldo_total      = float(CustomUser.objects.aggregate(t=Sum('saldo'))['t'] or 0)
    usuarios_activos = (
        CustomUser.objects
        .filter(compras__dia_comprado__gte=date.today() - timedelta(weeks=4))
        .distinct().count()
    )
    comentarios_sin_leer = Comentario.objects.filter(leido=False).count()

    # ── Línea temporal: últimas 8 semanas ──────────────────────────────────
    inicio = date.today() - timedelta(weeks=8)
    base_qs = Compra.objects.filter(retiro=True) if vista == 'entregas' else Compra.objects
    diarios_qs = (
        base_qs.filter(dia_comprado__gte=inicio)
        .values('dia_comprado').annotate(total=Count('id'))
        .order_by('dia_comprado')
    )
    diarios_dict = {r['dia_comprado']: r['total'] for r in diarios_qs}

    linea_labels, linea_data, linea_colors = [], [], []
    cur = inicio
    while cur <= date.today():
        if cur.weekday() < 5:
            linea_labels.append(cur.strftime('%d/%m'))
            linea_data.append(diarios_dict.get(cur, 0))
            linea_colors.append('rgba(220,53,69,0.9)' if cur == fecha else 'rgba(54,96,146,0.7)')
        cur += timedelta(days=1)

    # ── Distribución semanal ───────────────────────────────────────────────
    todos_diarios = base_qs.values('dia_comprado').annotate(total=Count('id'))
    by_wd = defaultdict(list)
    for r in todos_diarios:
        wd = r['dia_comprado'].weekday()
        if wd < 5:
            by_wd[wd].append(r['total'])

    sem_promedios, sem_maximos, sem_minimos = [], [], []
    tabla_semanal = []
    for i in range(5):
        counts = by_wd[i]
        if counts:
            p, mx, mn = round(mean(counts), 1), max(counts), min(counts)
            sem_promedios.append(p)
            sem_maximos.append(mx)
            sem_minimos.append(mn)
            tabla_semanal.append({'dia': DIAS[i], 'promedio': p, 'maximo': mx, 'minimo': mn, 'semanas': len(counts)})
        else:
            sem_promedios.append(None)
            sem_maximos.append(None)
            sem_minimos.append(None)
            tabla_semanal.append({'dia': DIAS[i], 'promedio': None, 'maximo': None, 'minimo': None, 'semanas': 0})

    # ── Índices VMDA ──────────────────────────────────────────────────────
    from django.db.models.functions import ExtractHour

    # VMDA compras
    all_daily_c = list(Compra.objects.values('dia_comprado').annotate(total=Count('id')))
    all_counts_c = [r['total'] for r in all_daily_c]
    vmda_compras = round(mean(all_counts_c), 1) if all_counts_c else 1

    # VMDA retiros
    all_daily_r = list(
        Compra.objects.filter(retiro=True)
        .values('dia_comprado').annotate(total=Count('id'))
    )
    all_counts_r = [r['total'] for r in all_daily_r]
    vmda_retiros = round(mean(all_counts_r), 1) if all_counts_r else 1

    # Índice mensual — basado en retiros
    by_month = defaultdict(list)
    for r in all_daily_r:
        by_month[r['dia_comprado'].month].append(r['total'])
    MESES = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic']
    idx_mensual = [
        round(mean(by_month[m]) / vmda_retiros * 100, 1) if by_month[m] else None
        for m in range(1, 13)
    ]

    # Índice semanal — basado en retiros
    by_wd_all = defaultdict(list)
    for r in all_daily_r:
        wd = r['dia_comprado'].weekday()
        if wd < 5:
            by_wd_all[wd].append(r['total'])
    all_wd = [c for wd in range(5) for c in by_wd_all[wd]]
    weekly_avg_all = mean(all_wd) if all_wd else 1
    idx_semanal = [
        round(mean(by_wd_all[wd]) / weekly_avg_all * 100, 1) if by_wd_all[wd] else None
        for wd in range(5)
    ]

    # Índice horario (retiros con hora_retiro)
    hourly_qs = (
        Compra.objects
        .filter(hora_retiro__isnull=False)
        .annotate(h=ExtractHour('hora_retiro'))
        .values('h', 'dia_comprado')
        .annotate(cnt=Count('id'))
    )
    by_hour = defaultdict(list)
    for r in hourly_qs:
        by_hour[r['h']].append(r['cnt'])
    all_hours = sorted(by_hour.keys())
    if all_hours:
        total_daily_retiro = sum(mean(by_hour[h]) for h in all_hours)
        expected_per_hour = total_daily_retiro / len(all_hours)
        idx_horario = [round(mean(by_hour[h]) / expected_per_hour * 100, 1) for h in all_hours]
        hora_labels = [f'{h:02d}:00' for h in all_hours]
    else:
        idx_horario, hora_labels = [], []

    return {
        # KPIs
        'fecha': fecha,
        'vista': vista,
        'compras_dia': compras_dia,
        'entregas_dia': entregas_dia,
        'saldo_total': saldo_total,
        'usuarios_activos': usuarios_activos,
        'comentarios_sin_leer': comentarios_sin_leer,
        # JSON para charts
        'json_linea_labels':   json.dumps(linea_labels),
        'json_linea_data':     json.dumps(linea_data),
        'json_linea_colors':   json.dumps(linea_colors),
        'json_menu_data':      json.dumps(por_menu),
        'json_turno_data':     json.dumps(por_turno),
        'json_cargas_data':    json.dumps(list(cargas_metodo.values())),
        'tabla_semanal':       tabla_semanal,
        'json_sem_labels':     json.dumps(DIAS_CORTO),
        'json_sem_promedios':  json.dumps(sem_promedios),
        'json_sem_maximos':    json.dumps(sem_maximos),
        'json_sem_minimos':    json.dumps(sem_minimos),
        # índices VMDA
        'vmda_compras': vmda_compras,
        'vmda_retiros': vmda_retiros,
        'json_idx_mensual':  json.dumps(idx_mensual),
        'json_meses_labels': json.dumps(MESES),
        'json_idx_semanal':  json.dumps(idx_semanal),
        'json_idx_horario':  json.dumps(idx_horario),
        'json_hora_labels':  json.dumps(hora_labels),
        # para exportar excel
        'by_wd': by_wd,
        'diarios_dict': diarios_dict,
        'DIAS': DIAS,
    }


class DashboardView(AdministradorRequiredMixin, View):

    template_name = 'admin_panel/dashboard.html'

    def get(self, request):
        fecha_str = request.GET.get('fecha')
        vista = request.GET.get('vista', 'compras')
        try:
            fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date() if fecha_str else date.today()
        except ValueError:
            fecha = date.today()

        context = {'titulo': 'Dashboard', **_dashboard_data(fecha, vista)}
        return render(request, self.template_name, context)


class DashboardExportView(AdministradorRequiredMixin, View):

    def get(self, request):
        fecha_str = request.GET.get('fecha')
        vista = request.GET.get('vista', 'compras')
        try:
            fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date() if fecha_str else date.today()
        except ValueError:
            fecha = date.today()

        data = _dashboard_data(fecha, vista)
        DIAS = data['DIAS']

        wb = openpyxl.Workbook()
        hf = PatternFill(start_color='366092', end_color='366092', fill_type='solid')
        hfont = Font(color='FFFFFF', bold=True)

        def _header(ws, cols):
            for j, h in enumerate(cols, 1):
                c = ws.cell(row=1, column=j, value=h)
                c.fill = hf; c.font = hfont
                c.alignment = Alignment(horizontal='center')

        def _autofit(ws):
            for i, col in enumerate(ws.columns, 1):
                mx = max((len(str(cell.value or '')) for cell in col
                          if not isinstance(cell, MergedCell)), default=8)
                ws.column_dimensions[get_column_letter(i)].width = mx + 4

        # ── Hoja 1: Compras diarias ────────────────────────────────────────
        ws1 = wb.active
        ws1.title = 'Compras diarias'
        _header(ws1, ['Fecha', 'Día', 'Compras' if vista == 'compras' else 'Entregas'])
        inicio = date.today() - timedelta(weeks=8)
        cur = inicio
        row = 2
        dias_es = ['Lunes','Martes','Miércoles','Jueves','Viernes','Sábado','Domingo']
        while cur <= date.today():
            if cur.weekday() < 5:
                ws1.append([
                    cur.strftime('%d/%m/%Y'),
                    dias_es[cur.weekday()],
                    data['diarios_dict'].get(cur, 0),
                ])
            cur += timedelta(days=1)
        _autofit(ws1)

        # ── Hoja 2: Distribución semanal ──────────────────────────────────
        ws2 = wb.create_sheet('Distribución semanal')
        _header(ws2, ['Día', 'Promedio', 'Máximo', 'Mínimo', 'Semanas con datos'])
        for i in range(5):
            counts = data['by_wd'][i]
            ws2.append([
                DIAS[i],
                round(mean(counts), 1) if counts else '-',
                max(counts) if counts else '-',
                min(counts) if counts else '-',
                len(counts),
            ])
        _autofit(ws2)

        # ── Hoja 3: Sistema ───────────────────────────────────────────────
        ws3 = wb.create_sheet('Sistema')
        ws3.append(['Métrica', 'Valor'])
        ws3['A1'].font = Font(bold=True); ws3['B1'].font = Font(bold=True)
        ws3.append(['Fecha consultada', fecha.strftime('%d/%m/%Y')])
        ws3.append(['Compras en la fecha', data['compras_dia']])
        ws3.append(['Entregas en la fecha', data['entregas_dia']])
        ws3.append(['Saldo total en el sistema', f"${data['saldo_total']:,.0f}"])
        ws3.append(['Usuarios activos (últimas 4 sem.)', data['usuarios_activos']])
        ws3.append(['Comentarios sin leer', data['comentarios_sin_leer']])
        _autofit(ws3)

        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        nombre = f"Dashboard_{fecha.strftime('%Y-%m-%d')}_{vista}"
        response['Content-Disposition'] = f'attachment; filename="{nombre}.xlsx"'
        wb.save(response)
        return response
