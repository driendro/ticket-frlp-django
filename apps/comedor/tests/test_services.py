# apps/comedor/tests/test_services.py
import pytest
from datetime import date, time, timedelta
from unittest.mock import patch, MagicMock

from apps.comedor.services import (
    es_fecha_vianda_ordenable,
    comedor_activo,
    paso_corte_proxima_semana,
    get_lunes_de_semana,
    get_semanas_para_compra,
)


# ------------------------------------------------------------------ fixtures

@pytest.fixture
def config_base(db):
    """
    Configuración base del comedor.
    Apertura: 01/03 - Cierre: 30/11
    Receso: 14/07 - 25/07
    Corte: Viernes (5) a las 04:00
    """
    from apps.core.models import Configuracion
    return Configuracion.objects.create(
        apertura=date(2026, 3, 1),
        cierre=date(2026, 11, 30),
        vacaciones_inicio=date(2026, 7, 14),
        vacaciones_fin=date(2026, 7, 25),
        dia_inicial=1,
        dia_final=5,
        hora_final=time(4, 0, 0),
        permitir_ambos_turnos=False,
    )


@pytest.fixture
def usuario(db):
    from apps.accounts.models import CustomUser
    from apps.core.models import Precio
    Precio.objects.get_or_create(
        tipo_user='Estudiante', defaults={'costo': 500})
    return CustomUser.objects.create_user(
        username='12345678',
        documento=12345678,
        password='test1234',
        first_name='Juan',
        last_name='Pérez',
        email='juan@test.com',
        tipo='Estudiante',
        saldo=1000,
    )


# ------------------------------------------------------------------ get_lunes_de_semana

class TestGetLunesDeSemana:

    def test_lunes_es_el_mismo_dia(self):
        lunes = date(2026, 5, 4)  # lunes
        assert get_lunes_de_semana(lunes) == lunes

    def test_miercoles_retorna_lunes(self):
        miercoles = date(2026, 5, 6)
        lunes = date(2026, 5, 4)
        assert get_lunes_de_semana(miercoles) == lunes

    def test_viernes_retorna_lunes(self):
        viernes = date(2026, 5, 8)
        lunes = date(2026, 5, 4)
        assert get_lunes_de_semana(viernes) == lunes

    def test_domingo_retorna_lunes_anterior(self):
        domingo = date(2026, 5, 10)
        lunes = date(2026, 5, 4)
        assert get_lunes_de_semana(domingo) == lunes


# ------------------------------------------------------------------ comedor_activo

class TestComedorActivo:

    def test_activo_en_primer_semestre(self, config_base):
        with patch('apps.comedor.services.date') as mock_date:
            mock_date.today.return_value = date(2026, 5, 8)
            mock_date.side_effect = lambda *args, **kwargs: date(
                *args, **kwargs)
            assert comedor_activo() is True

    def test_inactivo_en_receso(self, config_base):
        with patch('apps.comedor.services.date') as mock_date:
            mock_date.today.return_value = date(2026, 7, 20)
            mock_date.side_effect = lambda *args, **kwargs: date(
                *args, **kwargs)
            assert comedor_activo() is False

    def test_inactivo_antes_de_apertura(self, config_base):
        with patch('apps.comedor.services.date') as mock_date:
            mock_date.today.return_value = date(2026, 1, 15)
            mock_date.side_effect = lambda *args, **kwargs: date(
                *args, **kwargs)
            assert comedor_activo() is False

    def test_inactivo_despues_de_cierre(self, config_base):
        with patch('apps.comedor.services.date') as mock_date:
            mock_date.today.return_value = date(2026, 12, 5)
            mock_date.side_effect = lambda *args, **kwargs: date(
                *args, **kwargs)
            assert comedor_activo() is False

    def test_sin_config_retorna_false(self, db):
        assert comedor_activo() is False


# ------------------------------------------------------------------ es_fecha_vianda_ordenable

class TestEsFechaViandaOrdenable:
    """
    Regla: una vianda de la semana N se puede pedir hasta el
    viernes (día 5) a las 04:00 de la semana N-1.

    Ejemplo:
    - Vianda: lunes 11/05
    - Corte: viernes 08/05 a las 04:00
    - Si ahora es jueves 07/05 23:00 → ordenable
    - Si ahora es viernes 08/05 03:59 → ordenable
    - Si ahora es viernes 08/05 04:01 → NO ordenable
    - Si ahora es sábado 09/05 → NO ordenable
    """

    def test_vianda_proxima_semana_antes_del_corte(self, config_base):
        # Hoy: jueves 07/05 a las 10:00
        # Vianda: lunes 11/05
        # Corte: viernes 08/05 04:00 → debe ser ordenable
        with patch('apps.comedor.services.datetime') as mock_dt:
            from datetime import datetime
            mock_dt.now.return_value = datetime(2026, 5, 7, 10, 0, 0)
            mock_dt.combine = datetime.combine
            assert es_fecha_vianda_ordenable(date(2026, 5, 11)) is True

    def test_vianda_proxima_semana_despues_del_corte(self, config_base):
        # Hoy: viernes 08/05 a las 05:00
        # Corte ya pasó (04:00) → NO ordenable
        with patch('apps.comedor.services.datetime') as mock_dt:
            from datetime import datetime
            mock_dt.now.return_value = datetime(2026, 5, 8, 5, 0, 0)
            mock_dt.combine = datetime.combine
            assert es_fecha_vianda_ordenable(date(2026, 5, 11)) is False

    def test_vianda_en_el_pasado(self, config_base):
        with patch('apps.comedor.services.datetime') as mock_dt:
            from datetime import datetime
            mock_dt.now.return_value = datetime(2026, 5, 8, 10, 0, 0)
            mock_dt.combine = datetime.combine
            assert es_fecha_vianda_ordenable(date(2026, 4, 20)) is False

    def test_vianda_en_receso(self, config_base):
        # Vianda durante receso invernal
        with patch('apps.comedor.services.datetime') as mock_dt:
            from datetime import datetime
            mock_dt.now.return_value = datetime(2026, 7, 5, 10, 0, 0)
            mock_dt.combine = datetime.combine
            assert es_fecha_vianda_ordenable(date(2026, 7, 20)) is False

    def test_vianda_fuera_del_periodo(self, config_base):
        # Vianda en enero, fuera del período del comedor
        with patch('apps.comedor.services.datetime') as mock_dt:
            from datetime import datetime
            mock_dt.now.return_value = datetime(2026, 1, 5, 10, 0, 0)
            mock_dt.combine = datetime.combine
            assert es_fecha_vianda_ordenable(date(2026, 1, 12)) is False

    def test_exactamente_en_el_corte(self, config_base):
        # Exactamente a las 04:00:00 del viernes → NO ordenable
        with patch('apps.comedor.services.datetime') as mock_dt:
            from datetime import datetime
            mock_dt.now.return_value = datetime(2026, 5, 8, 4, 0, 0)
            mock_dt.combine = datetime.combine
            assert es_fecha_vianda_ordenable(date(2026, 5, 11)) is False

    def test_un_segundo_antes_del_corte(self, config_base):
        # 03:59:59 del viernes → todavía ordenable
        with patch('apps.comedor.services.datetime') as mock_dt:
            from datetime import datetime
            mock_dt.now.return_value = datetime(2026, 5, 8, 3, 59, 59)
            mock_dt.combine = datetime.combine
            assert es_fecha_vianda_ordenable(date(2026, 5, 11)) is True

    def test_sin_config_retorna_false(self, db):
        assert es_fecha_vianda_ordenable(date(2026, 5, 11)) is False


# ------------------------------------------------------------------ paso_corte_proxima_semana

class TestPasoCorteProximaSemana:

    def test_lunes_no_paso_el_corte(self, config_base):
        # Lunes → no pasó el corte
        with patch('apps.comedor.services.datetime') as mock_dt:
            from datetime import datetime
            mock_dt.now.return_value = datetime(2026, 5, 4, 10, 0, 0)
            assert paso_corte_proxima_semana() is False

    def test_viernes_antes_del_corte(self, config_base):
        with patch('apps.comedor.services.datetime') as mock_dt:
            from datetime import datetime
            mock_dt.now.return_value = datetime(2026, 5, 8, 3, 0, 0)
            assert paso_corte_proxima_semana() is False

    def test_viernes_despues_del_corte(self, config_base):
        with patch('apps.comedor.services.datetime') as mock_dt:
            from datetime import datetime
            mock_dt.now.return_value = datetime(2026, 5, 8, 5, 0, 0)
            assert paso_corte_proxima_semana() is True

    def test_sabado_paso_el_corte(self, config_base):
        with patch('apps.comedor.services.datetime') as mock_dt:
            from datetime import datetime
            mock_dt.now.return_value = datetime(2026, 5, 9, 10, 0, 0)
            assert paso_corte_proxima_semana() is True
