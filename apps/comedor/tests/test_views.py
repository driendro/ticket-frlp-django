# apps/comedor/tests/test_views.py
import pytest
from datetime import date, time
from django.urls import reverse


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
def client_logueado(client, usuario):
    client.login(documento=12345678, password='test1234')
    return client


class TestLoginView:

    def test_get_login(self, client):
        response = client.get(reverse('accounts:login'))
        assert response.status_code == 200

    def test_login_exitoso(self, client, usuario):
        response = client.post(reverse('accounts:login'), {
            'documento': 12345678,
            'password': 'test1234',
        })
        assert response.status_code == 302
        assert response.url == reverse('comedor:index')

    def test_login_password_incorrecta(self, client, usuario):
        response = client.post(reverse('accounts:login'), {
            'documento': 12345678,
            'password': 'wrongpassword',
        })
        assert response.status_code == 200

    def test_login_documento_inexistente(self, client, db):
        response = client.post(reverse('accounts:login'), {
            'documento': 99999999,
            'password': 'test1234',
        })
        assert response.status_code == 200

    def test_login_redirige_si_ya_logueado(self, client_logueado):
        response = client_logueado.get(reverse('accounts:login'))
        assert response.status_code == 302


class TestIndexView:

    def test_redirige_si_no_logueado(self, client, db):
        response = client.get(reverse('comedor:index'))
        assert response.status_code == 302
        assert 'login' in response.url

    def test_comedor_cerrado_sin_config(self, client_logueado, db):
        response = client_logueado.get(reverse('comedor:index'))
        assert response.status_code == 200
        assert 'cerrado' in response.templates[0].name

    def test_comedor_abierto_con_config(self, client_logueado, config_base):
        from unittest.mock import patch
        from datetime import datetime
        with patch('apps.comedor.services.datetime') as mock_dt:
            mock_dt.now.return_value = datetime(2026, 5, 8, 10, 0, 0)
            mock_dt.combine = datetime.combine
            with patch('apps.comedor.services.date') as mock_date:
                mock_date.today.return_value = date(2026, 5, 8)
                mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
                response = client_logueado.get(reverse('comedor:index'))
        assert response.status_code == 200
        assert 'semanas' in response.context


class TestDevolverCompraView:

    def test_get_sin_compras(self, client_logueado, config_base):
        response = client_logueado.get(reverse('comedor:devolver'))
        assert response.status_code == 200
        assert len(response.context['compras']) == 0

    def test_post_sin_seleccion(self, client_logueado, config_base):
        response = client_logueado.post(
            reverse('comedor:devolver'),
            {}
        )
        assert response.status_code == 302
