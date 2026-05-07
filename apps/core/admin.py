# apps/core/admin.py
from django.contrib import admin
from .models import Precio, Configuracion, Feriado, Menu, Comentario


@admin.register(Precio)
class PrecioAdmin(admin.ModelAdmin):
    list_display = ['tipo_user', 'costo']


@admin.register(Configuracion)
class ConfiguracionAdmin(admin.ModelAdmin):
    list_display = ['apertura', 'cierre',
                    'dia_inicial', 'dia_final', 'hora_final']

    def has_add_permission(self, request):
        # Solo permite un registro
        return not Configuracion.objects.exists()


@admin.register(Feriado)
class FeriadoAdmin(admin.ModelAdmin):
    list_display = ['fecha', 'detalle']
    search_fields = ['detalle']
    list_filter = ['fecha']


@admin.register(Menu)
class MenuAdmin(admin.ModelAdmin):
    list_display = ['dia', 'menu_basico', 'menu_veggie', 'menu_sin_tacc']


@admin.register(Comentario)
class ComentarioAdmin(admin.ModelAdmin):
    list_display = ['usuario', 'fecha', 'hora']
    search_fields = ['comentario', 'usuario__last_name']
