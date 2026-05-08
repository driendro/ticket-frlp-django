# apps/accounts/tests/test_views.py
import pytest
from django.urls import reverse


@pytest.fixture
def usuario(db):
    from apps.accounts.models import CustomUser
    return CustomUser.objects.create_user(
        username='12345678',
        documento=12345678,
        password='test1234',
        first_name='Juan',
        last_name='Pérez',
        email='juan@test.com',
        tipo='Estudiante',
        saldo=0,
    )


class TestCambiarPasswordView:

    def test_get_requiere_login(self, client):
        response = client.get(reverse('accounts:cambiar_password'))
        assert response.status_code == 302

    def test_cambio_exitoso(self, client, usuario):
        client.login(documento=12345678, password='test1234')
        response = client.post(reverse('accounts:cambiar_password'), {
            'password_anterior': 'test1234',
            'password_nuevo': 'nueva1234',
            'password_confirmado': 'nueva1234',
        })
        assert response.status_code == 302
        usuario.refresh_from_db()
        assert usuario.check_password('nueva1234')

    def test_password_anterior_incorrecta(self, client, usuario):
        client.login(documento=12345678, password='test1234')
        response = client.post(reverse('accounts:cambiar_password'), {
            'password_anterior': 'incorrecta',
            'password_nuevo': 'nueva1234',
            'password_confirmado': 'nueva1234',
        })
        assert response.status_code == 200
        usuario.refresh_from_db()
        assert usuario.check_password('test1234')

    def test_passwords_nuevas_no_coinciden(self, client, usuario):
        client.login(documento=12345678, password='test1234')
        response = client.post(reverse('accounts:cambiar_password'), {
            'password_anterior': 'test1234',
            'password_nuevo': 'nueva1234',
            'password_confirmado': 'diferente1234',
        })
        assert response.status_code == 200
        usuario.refresh_from_db()
        assert usuario.check_password('test1234')
