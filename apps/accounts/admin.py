# apps/accounts/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ['documento', 'first_name',
                    'last_name', 'tipo', 'saldo', 'is_active']
    search_fields = ['documento', 'first_name', 'last_name']

    fieldsets = UserAdmin.fieldsets + (
        ('Datos UTN', {
            'fields': ('tipo', 'legajo', 'documento', 'especialidad', 'saldo', 'es_becado')
        }),
    )
