# apps/accounts/models.py
from django.db import models
from django.contrib.auth.models import AbstractUser


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

    USERNAME_FIELD = 'documento'
    REQUIRED_FIELDS = ['username', 'email']

    class Meta:
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'

    def __str__(self):
        return f"{self.last_name}, {self.first_name} - DNI: {self.documento}"

    @property
    def nombre(self):
        return self.first_name

    @property
    def apellido(self):
        return self.last_name

    @property
    def nombre_completo(self):
        return f"{self.last_name}, {self.first_name}"

    def get_precio(self):
        """Retorna el costo de la vianda según tipo y beca."""
        from apps.core.models import Precio
        tipo = 'Becado' if self.es_becado else self.tipo
        try:
            return Precio.objects.get(tipo_user=tipo).costo
        except Precio.DoesNotExist:
            return 0
