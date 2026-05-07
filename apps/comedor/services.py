from datetime import datetime, date, timedelta
from django.db import transaction
import json

from apps.core.models import Configuracion, Feriado
from .models import Compra, Transaccion, LogCompra


def get_lunes_de_semana(fecha: date) -> date:
    """Retorna el lunes de la semana a la que pertenece la fecha."""
    return fecha - timedelta(days=fecha.weekday())


def comedor_activo() -> bool:
    """
    Equivale a estadoComedor() de CI3.
    Verifica si el comedor está operativo en la fecha actual.
    """
    config = Configuracion.get()
    if not config:
        return False

    hoy = date.today()

    primer_semestre = config.apertura <= hoy <= config.vacaciones_inicio
    segundo_semestre = config.vacaciones_fin <= hoy <= config.cierre

    return primer_semestre or segundo_semestre


def es_fecha_vianda_ordenable(fecha_vianda: date) -> bool:
    """
    Equivale a esFechaViandaAunOrdenable() de CI3.
    Determina si una fecha de vianda todavía puede ser ordenada
    según las reglas de corte semanal.
    """
    config = Configuracion.get()
    if not config:
        return False

    ahora = datetime.now()
    hoy = ahora.date()

    # Si la fecha ya pasó no es ordenable
    if fecha_vianda < hoy:
        return False

    # Verificar períodos generales del comedor
    primer_semestre = config.apertura <= fecha_vianda <= config.vacaciones_inicio
    segundo_semestre = config.vacaciones_fin <= fecha_vianda <= config.cierre
    es_periodo_valido = primer_semestre or segundo_semestre

    if not es_periodo_valido:
        return False

    # Calcular fecha y hora de corte para esta vianda
    # El corte ocurre en la semana ANTERIOR a la de la vianda
    lunes_semana_vianda = get_lunes_de_semana(fecha_vianda)
    lunes_semana_anterior = lunes_semana_vianda - timedelta(weeks=1)

    # Avanzar al día de corte dentro de esa semana anterior
    # dia_final: 1=Lunes, 2=Martes, ... 5=Viernes
    dia_corte = lunes_semana_anterior + timedelta(days=config.dia_final - 1)

    # Combinar fecha y hora de corte
    fecha_hora_corte = datetime.combine(dia_corte, config.hora_final)

    return ahora <= fecha_hora_corte


def paso_corte_proxima_semana() -> bool:
    """
    Determina si ya pasó el horario de corte para ordenar
    viandas de la próxima semana.
    """
    config = Configuracion.get()
    if not config:
        return False

    ahora = datetime.now()
    dia_actual = ahora.isoweekday()  # 1=Lunes, 7=Domingo

    if dia_actual > config.dia_final:
        return True

    if dia_actual == config.dia_final:
        hora_actual = ahora.time()
        return hora_actual >= config.hora_final

    return False


def get_feriados_en_rango(fecha_inicio: date, fecha_fin: date) -> set:
    """Retorna un set de fechas de feriados en el rango dado."""
    feriados = Feriado.objects.filter(
        fecha__gte=fecha_inicio,
        fecha__lte=fecha_fin
    ).values_list('fecha', flat=True)
    return set(feriados)


def get_compras_usuario_en_rango(usuario, fecha_inicio: date, fecha_fin: date) -> dict:
    """
    Retorna un dict con las compras del usuario en el rango.
    Estructura: {fecha: {turno: menu}}
    """
    compras = Compra.objects.filter(
        usuario=usuario,
        dia_comprado__gte=fecha_inicio,
        dia_comprado__lte=fecha_fin
    ).values('dia_comprado', 'turno', 'menu')

    resultado = {}
    for compra in compras:
        fecha = compra['dia_comprado']
        if fecha not in resultado:
            resultado[fecha] = {}
        resultado[fecha][compra['turno']] = compra['menu']

    return resultado


def get_semanas_para_compra(usuario, n_semanas: int = 5) -> list:
    """
    Genera los datos de las semanas para mostrar en la vista de compra.
    Equivale a la lógica del index() de Ticket.php en CI3.
    Retorna una lista de semanas, cada una con sus días y estados.
    """
    config = Configuracion.get()
    if not config:
        return []

    hoy = date.today()
    lunes_semana_actual = get_lunes_de_semana(hoy)
    ya_paso_corte = paso_corte_proxima_semana()

    # Calcular rango total de fechas
    fecha_inicio = lunes_semana_actual
    fecha_fin = lunes_semana_actual + \
        timedelta(weeks=n_semanas) + timedelta(days=4)

    feriados = get_feriados_en_rango(fecha_inicio, fecha_fin)
    compras_usuario = get_compras_usuario_en_rango(
        usuario, fecha_inicio, fecha_fin)

    DIAS_ES = ['lunes', 'martes', 'miércoles',
               'jueves', 'viernes', 'sábado', 'domingo']
    MESES_ES = {
        'January': 'Enero', 'February': 'Febrero', 'March': 'Marzo',
        'April': 'Abril', 'May': 'Mayo', 'June': 'Junio',
        'July': 'Julio', 'August': 'Agosto', 'September': 'Septiembre',
        'October': 'Octubre', 'November': 'Noviembre', 'December': 'Diciembre'
    }

    semanas = []

    for w in range(n_semanas):
        lunes = lunes_semana_actual + timedelta(weeks=w)
        viernes = lunes + timedelta(days=4)

        # Formatear fechas en español
        inicio_str = lunes.strftime('%d de %B').replace(
            lunes.strftime('%B'), MESES_ES[lunes.strftime('%B')]
        )
        fin_str = viernes.strftime('%d de %B').replace(
            viernes.strftime('%B'), MESES_ES[viernes.strftime('%B')]
        )

        dias = []
        for d in range(5):  # Lunes a Viernes
            dia = lunes + timedelta(days=d)
            dia_str = dia.strftime('%Y-%m-%d')

            es_feriado = dia in feriados
            es_receso = config.vacaciones_inicio < dia < config.vacaciones_fin
            es_pasado = dia < hoy

            compras_dia = compras_usuario.get(dia, {})
            comprado_manana = 'manana' in compras_dia
            comprado_noche = 'noche' in compras_dia

            # Deshabilitar por semana
            if w == 0:
                # Semana actual siempre deshabilitada para comprar
                deshabilitar_manana = True
                deshabilitar_noche = True
            elif w == 1 and ya_paso_corte:
                # Próxima semana deshabilitada si pasó el corte
                deshabilitar_manana = True
                deshabilitar_noche = True
            else:
                deshabilitar_manana = (
                    comprado_manana or es_feriado or
                    es_receso or es_pasado
                )
                deshabilitar_noche = (
                    comprado_noche or es_feriado or
                    es_receso or es_pasado
                )

            dias.append({
                'nombre': DIAS_ES[dia.weekday()],
                'fecha_display': dia.day,
                'fecha_ymd': dia_str,
                'comprado_manana': comprado_manana,
                'comprado_noche': comprado_noche,
                'menu_manana': compras_dia.get('manana'),
                'menu_noche': compras_dia.get('noche'),
                'es_feriado': es_feriado,
                'es_receso': es_receso,
                'es_pasado': es_pasado,
                'deshabilitar_manana': deshabilitar_manana,
                'deshabilitar_noche': deshabilitar_noche,
            })

        semanas.append({
            'indice': w,
            'es_semana_actual': w == 0,
            'inicio': inicio_str,
            'fin': fin_str,
            'dias': dias,
        })

    return semanas


def procesar_compra_con_saldo(compra_pendiente, monto_total: float) -> bool:
    """
    Procesa una compra usando saldo del usuario.
    Equivale a procesarCompraConSaldo() de CI3.
    """

    usuario = compra_pendiente.usuario

    with transaction.atomic():
        viandas = json.loads(compra_pendiente.datos)

        if not viandas:
            return False

        # Crear transacción principal
        saldo_actual = usuario.saldo
        saldo_final = saldo_actual - monto_total

        transaccion = Transaccion.objects.create(
            usuario=usuario,
            transaccion='Compra con saldo',
            monto=-monto_total,
            saldo=saldo_final,
            external_reference=compra_pendiente.external_reference
        )

        # Crear compras individuales
        for vianda in viandas:
            Compra.objects.create(
                usuario=usuario,
                dia_comprado=vianda['dia_comprado'],
                precio=vianda['precio'],
                turno=vianda['turno'],
                menu=vianda['menu'],
                tipo=vianda.get('tipo', ''),
                transaccion=transaccion,
                external_reference=compra_pendiente.external_reference
            )
            LogCompra.objects.create(
                usuario=usuario,
                dia_comprado=vianda['dia_comprado'],
                precio=vianda['precio'],
                turno=vianda['turno'],
                menu=vianda['menu'],
                tipo=vianda.get('tipo', ''),
                transaccion_tipo='Compra con saldo',
                transaccion=transaccion,
                external_reference=compra_pendiente.external_reference
            )

        # Actualizar saldo
        usuario.saldo = saldo_final
        usuario.save(update_fields=['saldo'])

        # Marcar compra pendiente como procesada
        compra_pendiente.procesada = True
        compra_pendiente.mp_estado = 'approved'
        compra_pendiente.save(update_fields=['procesada', 'mp_estado'])

    return True
