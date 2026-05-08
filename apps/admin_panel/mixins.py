# apps/admin_panel/mixins.py
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.contrib import messages


class AdminRequiredMixin(LoginRequiredMixin):
    """Requiere que el usuario sea staff de Django."""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not request.user.is_staff:
            messages.error(request, 'No tenés permisos para acceder.')
            return redirect('comedor:index')
        return super().dispatch(request, *args, **kwargs)


class CajeroRequiredMixin(AdminRequiredMixin):
    """Nivel 0 y 1: cajero y administrador."""

    def dispatch(self, request, *args, **kwargs):
        result = super().dispatch(request, *args, **kwargs)
        if hasattr(result, 'status_code') and result.status_code == 302:
            return result
        if not request.user.groups.filter(
            name__in=['cajero', 'administrador']
        ).exists() and not request.user.is_superuser:
            messages.error(request, 'No tenés permisos de cajero.')
            return redirect('comedor:index')
        return result


class AdministradorRequiredMixin(AdminRequiredMixin):
    """Solo nivel 1: administrador."""

    def dispatch(self, request, *args, **kwargs):
        result = super().dispatch(request, *args, **kwargs)
        if hasattr(result, 'status_code') and result.status_code == 302:
            return result
        if not request.user.groups.filter(
            name='administrador'
        ).exists() and not request.user.is_superuser:
            messages.error(request, 'No tenés permisos de administrador.')
            return redirect('admin_panel:index')
        return result


class RepartidorRequiredMixin(AdminRequiredMixin):
    """Solo nivel 2: repartidor."""

    def dispatch(self, request, *args, **kwargs):
        result = super().dispatch(request, *args, **kwargs)
        if hasattr(result, 'status_code') and result.status_code == 302:
            return result
        if not request.user.groups.filter(
            name='repartidor'
        ).exists() and not request.user.is_superuser:
            messages.error(request, 'No tenés permisos de repartidor.')
            return redirect('admin_panel:index')
        return result
