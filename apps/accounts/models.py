# apps/accounts/models.py
from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):

    TIPO_CHOICES = [
        ('Estudiante', 'Estudiante'),
        ('Docente', 'Docente'),
        ('No Docente', 'No Docente'),
    ]

    ESPECIALIDAD_CHOICES = [
        ('Civil', 'Civil'),
        ('Electrica', 'Eléctrica'),
        ('Industrial', 'Industrial'),
        ('Mecanica', 'Mecánica'),
        ('Quimica', 'Química'),
        ('Sistemas', 'Sistemas'),
    ]

    # Campos del sistema original
    tipo = models.CharField(
        max_length=20, choices=TIPO_CHOICES, default='Estudiante')
    legajo = models.IntegerField(unique=True, null=True, blank=True)
    documento = models.IntegerField(unique=True)
    especialidad = models.CharField(
        max_length=20,
        choices=ESPECIALIDAD_CHOICES,
        null=True,
        blank=True
    )
    saldo = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    es_becado = models.BooleanField(default=False)

    # Hacemos que el login sea por documento
    USERNAME_FIELD = 'documento'
    REQUIRED_FIELDS = ['username', 'email']

    class Meta:
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'

    def __str__(self):
        return f"{self.apellido}, {self.first_name} - DNI: {self.documento}"

    @property
    def nombre(self):
        return self.first_name

    @property
    def apellido(self):
        return self.last_name

    @property
    def nombre_completo(self):
        return f"{self.last_name}, {self.first_name}"
