# apps/pagos/tests/test_services.py
import pytest
import json
from datetime import date, time
from unittest.mock import patch, MagicMock


@pytest.fixture
def config_base(db):
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
        tipo_user='Estudiante',
        defaults={'costo': 500}
    )
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


@pytest.fixture
def compra_pendiente(db, usuario):
    from apps.pagos.models import CompraPendiente
    seleccion = [
        {
            'dia_comprado': '2026-05-11',
            'turno': 'manana',
            'menu': 'Basico',
            'precio': 500,
            'tipo': 'Comer aqui',
        }
    ]
    return CompraPendiente.objects.create(
        usuario=usuario,
        external_reference='12345678-1234567890',
        datos=json.dumps(seleccion),
        total=500,
        mp_estado='pasarela',
    )


class TestCrearCompraPendiente:

    def test_crea_correctamente(self, db, usuario):
        from apps.pagos.services import crear_compra_pendiente
        seleccion = [{
            'dia_comprado': '2026-05-11',
            'turno': 'manana',
            'menu': 'Basico',
            'precio': 500,
        }]
        compra = crear_compra_pendiente(usuario, seleccion, 500)

        assert compra.usuario == usuario
        assert compra.total == 500
        assert compra.procesada is False
        assert compra.external_reference is not None

    def test_external_reference_unica(self, db, usuario):
        from apps.pagos.services import crear_compra_pendiente
        seleccion = [{'dia_comprado': '2026-05-11', 'turno': 'manana',
                      'menu': 'Basico', 'precio': 500}]
        compra1 = crear_compra_pendiente(usuario, seleccion, 500)
        compra2 = crear_compra_pendiente(usuario, seleccion, 500)
        assert compra1.external_reference != compra2.external_reference


class TestProcesarCompraConSaldo:

    def test_procesa_correctamente(self, db, usuario, compra_pendiente, config_base):
        from apps.comedor.services import procesar_compra_con_saldo
        from apps.comedor.models import Compra, Transaccion

        saldo_inicial = float(usuario.saldo)
        ok = procesar_compra_con_saldo(compra_pendiente, 500)

        assert ok is True

        usuario.refresh_from_db()
        assert float(usuario.saldo) == saldo_inicial - 500

        assert Compra.objects.filter(
            usuario=usuario,
            dia_comprado='2026-05-11'
        ).exists()

        assert Transaccion.objects.filter(
            usuario=usuario,
            transaccion='Compra con saldo'
        ).exists()

    def test_no_procesa_dos_veces(self, db, usuario, compra_pendiente, config_base):
        from apps.comedor.services import procesar_compra_con_saldo
        from apps.comedor.models import Compra

        procesar_compra_con_saldo(compra_pendiente, 500)
        compra_pendiente.refresh_from_db()
        assert compra_pendiente.procesada is True

        # La compra fue eliminada, no hay duplicado
        count = Compra.objects.filter(
            usuario=usuario,
            dia_comprado='2026-05-11'
        ).count()
        assert count == 1


class TestGetPasarelaActiva:

    def test_retorna_compra_activa(self, db, usuario, compra_pendiente):
        from apps.pagos.models import CompraPendiente
        resultado = CompraPendiente.get_pasarela_activa(usuario)
        assert resultado == compra_pendiente

    def test_retorna_none_si_no_hay(self, db, usuario):
        from apps.pagos.models import CompraPendiente
        resultado = CompraPendiente.get_pasarela_activa(usuario)
        assert resultado is None

    def test_no_retorna_procesadas(self, db, usuario, compra_pendiente):
        from apps.pagos.models import CompraPendiente
        compra_pendiente.procesada = True
        compra_pendiente.save()
        resultado = CompraPendiente.get_pasarela_activa(usuario)
        assert resultado is None
