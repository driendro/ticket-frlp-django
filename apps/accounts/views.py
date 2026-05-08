# apps/accounts/views.py
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.views import View


class LoginView(View):

    template_name = 'accounts/login.html'

    def get(self, request):
        if request.user.is_authenticated:
            return redirect('comedor:index')
        return render(request, self.template_name)

    def post(self, request):
        documento = request.POST.get('documento')
        password = request.POST.get('password')

        if not documento or not password:
            messages.error(request, 'Ingresá tu documento y contraseña.')
            return render(request, self.template_name)

        try:
            documento = int(documento)
        except ValueError:
            messages.error(request, 'El documento debe ser numérico.')
            return render(request, self.template_name)

        user = authenticate(request, documento=documento, password=password)

        if user is None:
            messages.error(request, 'Documento o contraseña incorrectos.')
            return render(request, self.template_name)

        if not user.is_active:
            messages.error(request, 'Tu cuenta está desactivada.')
            return render(request, self.template_name)

        login(request, user)
        return redirect('comedor:index')


class LogoutView(View):

    def get(self, request):
        logout(request)
        return redirect('accounts:login')


class CambiarPasswordView(LoginRequiredMixin, View):

    template_name = 'accounts/cambiar_password.html'

    def get(self, request):
        return render(request, self.template_name, {
            'titulo': 'Cambiar Contraseña'
        })

    def post(self, request):
        password_anterior = request.POST.get('password_anterior')
        password_nuevo = request.POST.get('password_nuevo')
        password_confirmado = request.POST.get('password_confirmado')

        if not request.user.check_password(password_anterior):
            messages.error(request, 'La contraseña actual es incorrecta.')
            return render(request, self.template_name, {
                'titulo': 'Cambiar Contraseña'
            })

        if password_nuevo != password_confirmado:
            messages.error(request, 'Las contraseñas nuevas no coinciden.')
            return render(request, self.template_name, {
                'titulo': 'Cambiar Contraseña'
            })

        if len(password_nuevo) < 6:
            messages.error(
                request, 'La contraseña debe tener al menos 6 caracteres.')
            return render(request, self.template_name, {
                'titulo': 'Cambiar Contraseña'
            })

        request.user.set_password(password_nuevo)
        request.user.save()

        # Mantener sesión activa después del cambio
        update_session_auth_hash(request, request.user)

        messages.success(request, 'Contraseña actualizada correctamente.')
        return redirect('accounts:cambiar_password')
