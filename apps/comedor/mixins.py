from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.contrib import messages


class CompradorRequiredMixin(LoginRequiredMixin):

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not request.user.es_comprador:
            messages.error(request, 'No tenés permisos para acceder a esa sección.')
            return redirect(request.user.home_url)
        return super().dispatch(request, *args, **kwargs)
