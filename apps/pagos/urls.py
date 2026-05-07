# apps/pagos/urls.py
from django.urls import path
from . import views

app_name = 'pagos'

urlpatterns = [
    path('procesar/', views.ProcesarCompraView.as_view(), name='procesar'),
    path('exitoso/', views.CompraExitosaView.as_view(), name='exitoso'),
    path('fallido/', views.CompraFallidaView.as_view(), name='fallido'),
    path('pendiente/', views.CompraPendienteView.as_view(), name='pendiente'),
    path('cancelar/', views.CancelarCompraAjaxView.as_view(), name='cancelar'),
    path('webhook/', views.WebhookMercadoPagoView.as_view(), name='webhook'),
]
