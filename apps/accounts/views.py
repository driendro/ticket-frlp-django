# apps/accounts/views.py
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
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
