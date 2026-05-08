# apps/comedor/views.py
from .models import Compra, Transaccion
from datetime import date, timedelta
from django.core.paginator import Paginator
from django.shortcuts import render, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.views import View
from django.utils import timezone

from apps.core.models import Configuracion
from .services import (
    comedor_activo,
    get_semanas_para_compra,
    es_fecha_vianda_ordenable,
    procesar_compra_con_saldo,
    get_lunes_de_semana,
    paso_corte_proxima_semana,
    get_feriados_en_rango,
)
from .models import Compra


class IndexView(LoginRequiredMixin, View):

    template_name = 'comedor/index.html'

    def get(self, request):
        usuario = request.user
        config = Configuracion.get()

        if not comedor_activo():
            return render(request, 'comedor/cerrado.html', {
                'titulo': 'Comprar Viandas'
            })

        semanas = get_semanas_para_compra(usuario)
        costo_vianda = usuario.get_precio()

        context = {
            'titulo': 'Comprar Viandas',
            'usuario': usuario,
            'semanas': semanas,
            'costo_vianda': float(costo_vianda),
            'permitir_ambos_turnos': config.permitir_ambos_turnos if config else False,
        }
        return render(request, self.template_name, context)

    def post(self, request):
        usuario = request.user
        costo_vianda = usuario.get_precio()

        post_menus = request.POST
        seleccion = []
        errores = []

        config = Configuracion.get()
        permitir_ambos_turnos = config.permitir_ambos_turnos if config else False

        # Procesar selección del formulario
        # El formulario envía selectMenu[fecha][turno] = menu
        fechas_procesadas = {}
        for key, value in post_menus.items():
            if not key.startswith('selectMenu['):
                continue
            if value == 'seleccionar' or not value:
                continue

            # Parsear key: selectMenu[2025-01-20][manana]
            try:
                partes = key.replace(
                    'selectMenu[', '').replace(']', ' ').split()
                fecha_str = partes[0]
                turno = partes[1]
            except (IndexError, ValueError):
                continue

            if fecha_str not in fechas_procesadas:
                fechas_procesadas[fecha_str] = {}
            fechas_procesadas[fecha_str][turno] = value

        for fecha_str, turnos in fechas_procesadas.items():
            # Validar que no se compren ambos turnos si no está permitido
            if not permitir_ambos_turnos and len(turnos) > 1:
                errores.append(
                    f"Para el día {fecha_str} solo podés seleccionar un turno."
                )
                continue

            for turno, menu in turnos.items():
                seleccion.append({
                    'dia_comprado': fecha_str,
                    'turno': turno,
                    'menu': menu,
                    'precio': float(costo_vianda),
                    'tipo': 'Comer aqui',
                })

        if errores:
            for error in errores:
                messages.error(request, error)
            return redirect('comedor:index')

        if not seleccion:
            messages.warning(request, 'No seleccionaste ninguna vianda.')
            return redirect('comedor:index')

        # Verificar conflictos con compras existentes
        for item in seleccion:
            existe = Compra.objects.filter(
                usuario=usuario,
                dia_comprado=item['dia_comprado'],
                turno=item['turno']
            ).exists()
            if existe:
                errores.append(
                    f"Ya tenés una vianda comprada para el {item['dia_comprado']} "
                    f"turno {item['turno']}."
                )

        if errores:
            for error in errores:
                messages.error(request, error)
            return redirect('comedor:index')

        # Guardar en sesión y redirigir a pagos
        import json
        total = sum(item['precio'] for item in seleccion)
        request.session['seleccion_compra'] = json.dumps(seleccion)
        request.session['total_compra'] = float(total)

        return redirect('pagos:procesar')


# apps/comedor/views.py - agregar estas vistas al archivo existente


class DevolverCompraView(LoginRequiredMixin, View):

    template_name = 'comedor/devolver_compra.html'

    def get_compras_devolvibles(self, usuario):
        """
        Retorna las compras que el usuario puede devolver.
        Misma lógica que devolverCompra() de CI3.
        """
        hoy = date.today()
        lunes_actual = get_lunes_de_semana(hoy)
        ya_paso_corte = paso_corte_proxima_semana()

        if ya_paso_corte:
            fecha_inicio = lunes_actual + timedelta(weeks=2)
        else:
            fecha_inicio = lunes_actual + timedelta(weeks=1)

        # Hasta el viernes de la 4ta semana
        fecha_fin = lunes_actual + timedelta(weeks=4) + timedelta(days=4)

        if fecha_inicio > fecha_fin:
            fecha_fin = fecha_inicio

        feriados = get_feriados_en_rango(fecha_inicio, fecha_fin)

        compras = Compra.objects.filter(
            usuario=usuario,
            dia_comprado__gte=fecha_inicio,
            dia_comprado__lte=fecha_fin,
        ).order_by('dia_comprado')

        # Filtrar feriados y receso
        from apps.core.models import Configuracion
        config = Configuracion.get()
        devolvibles = []

        for compra in compras:
            es_feriado = compra.dia_comprado in feriados
            es_receso = (
                config and
                config.vacaciones_inicio < compra.dia_comprado < config.vacaciones_fin
            )
            es_pasado = compra.dia_comprado < hoy

            if not es_feriado and not es_receso and not es_pasado:
                devolvibles.append(compra)

        return devolvibles

    def get(self, request):
        usuario = request.user
        compras = self.get_compras_devolvibles(usuario)

        context = {
            'titulo': 'Devolución de Compras',
            'compras': compras,
        }
        return render(request, self.template_name, context)

    def post(self, request):
        from django.db import transaction
        usuario = request.user
        ids_devolver = request.POST.getlist('devolver')

        if not ids_devolver:
            messages.warning(request, 'No seleccionaste ninguna vianda.')
            return redirect('comedor:devolver')

        compras_devolvibles = self.get_compras_devolvibles(usuario)
        ids_devolvibles = {str(c.id) for c in compras_devolvibles}

        # Verificar que los ids enviados sean válidos
        ids_validos = [i for i in ids_devolver if i in ids_devolvibles]

        if not ids_validos:
            messages.error(
                request, 'Las viandas seleccionadas no son válidas.')
            return redirect('comedor:devolver')

        with transaction.atomic():
            compras = Compra.objects.filter(
                id__in=ids_validos,
                usuario=usuario
            )
            monto_total = sum(c.precio for c in compras)
            nuevo_saldo = usuario.saldo + monto_total

            # Crear transacción
            transaccion = Transaccion.objects.create(
                usuario=usuario,
                transaccion='Devolucion',
                monto=monto_total,
                saldo=nuevo_saldo,
            )

            # Log y eliminación
            from .models import LogCompra
            for compra in compras:
                LogCompra.objects.create(
                    usuario=usuario,
                    dia_comprado=compra.dia_comprado,
                    precio=compra.precio,
                    turno=compra.turno,
                    menu=compra.menu,
                    tipo=compra.tipo,
                    transaccion_tipo='Devolucion',
                    transaccion=transaccion,
                )
                compra.delete()

            # Actualizar saldo
            usuario.saldo = nuevo_saldo
            usuario.save(update_fields=['saldo'])

        messages.success(
            request,
            f'Se devolvieron {len(ids_validos)} vianda(s). '
            f'Se acreditaron ${monto_total} a tu saldo.'
        )
        return redirect('comedor:devolver')


class MovimientosView(LoginRequiredMixin, View):

    template_name = 'comedor/movimientos.html'

    def get(self, request):
        transacciones = Transaccion.objects.filter(
            usuario=request.user
        ).order_by('-fecha', '-hora')

        paginator = Paginator(transacciones, 10)
        page = request.GET.get('page', 1)
        transacciones_page = paginator.get_page(page)

        context = {
            'titulo': 'Últimos Movimientos',
            'transacciones': transacciones_page,
        }
        return render(request, self.template_name, context)


class MenuView(View):

    template_name = 'comedor/menu.html'

    def get(self, request):
        from apps.core.models import Menu
        menu = Menu.objects.all().order_by('dia')
        context = {
            'titulo': 'Menú Semanal',
            'menu': menu,
        }
        return render(request, self.template_name, context)


class FaqView(View):

    template_name = 'comedor/faq.html'

    def get(self, request):
        return render(request, self.template_name, {'titulo': 'Preguntas Frecuentes'})


class ContactoView(View):

    template_name = 'comedor/contacto.html'

    def get(self, request):
        return render(request, self.template_name, {'titulo': 'Contacto'})
