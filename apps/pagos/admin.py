# apps/pagos/admin.py
from django.contrib import admin
from .models import CompraPendiente


@admin.register(CompraPendiente)
class CompraPendienteAdmin(admin.ModelAdmin):
    list_display = ['usuario', 'external_reference',
                    'total', 'mp_estado', 'procesada', 'created_at']
    search_fields = ['usuario__last_name',
                     'usuario__documento', 'external_reference']
    list_filter = ['mp_estado', 'procesada']
    readonly_fields = ['external_reference', 'created_at']
