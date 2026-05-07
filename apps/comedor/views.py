# apps/comedor/views.py
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
            'costo_vianda': costo_vianda,
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
