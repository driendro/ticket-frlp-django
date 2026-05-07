# apps/comedor/admin.py
from django.contrib import admin
from .models import Compra, Transaccion, LogCompra, LogCarga


@admin.register(Compra)
class CompraAdmin(admin.ModelAdmin):
    list_display = ['usuario', 'dia_comprado',
                    'turno', 'menu', 'precio', 'retiro']
    search_fields = ['usuario__last_name', 'usuario__documento']
    list_filter = ['turno', 'menu', 'retiro', 'dia_comprado']


@admin.register(Transaccion)
class TransaccionAdmin(admin.ModelAdmin):
    list_display = ['usuario', 'transaccion', 'monto', 'saldo', 'fecha']
    search_fields = ['usuario__last_name', 'usuario__documento']
    list_filter = ['transaccion']


@admin.register(LogCompra)
class LogCompraAdmin(admin.ModelAdmin):
    list_display = ['usuario', 'dia_comprado', 'turno', 'menu', 'precio']
    search_fields = ['usuario__last_name', 'usuario__documento']


@admin.register(LogCarga)
class LogCargaAdmin(admin.ModelAdmin):
    list_display = ['usuario', 'monto', 'formato', 'fecha']
    search_fields = ['usuario__last_name', 'usuario__documento']
