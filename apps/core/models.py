# apps/core/models.py
from django.db import models


class Precio(models.Model):

    TIPO_CHOICES = [
        ('Estudiante', 'Estudiante'),
        ('Becado', 'Becado'),
        ('Docente', 'Docente'),
        ('No Docente', 'No Docente'),
    ]

    tipo_user = models.CharField(
        max_length=20, choices=TIPO_CHOICES, unique=True)
    costo = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        verbose_name = 'Precio'
        verbose_name_plural = 'Precios'

    def __str__(self):
        return f"{self.tipo_user} - ${self.costo}"


class Configuracion(models.Model):
    """
    Singleton - solo debe existir un registro.
    Equivale a la tabla 'configuracion' de CI3.
    """
    apertura = models.DateField()
    cierre = models.DateField()
    vacaciones_inicio = models.DateField()
    vacaciones_fin = models.DateField()
    dia_inicial = models.IntegerField(
        default=1,
        help_text='1=Lunes, 2=Martes, ... 5=Viernes'
    )
    dia_final = models.IntegerField(
        default=5,
        help_text='1=Lunes, 2=Martes, ... 5=Viernes'
    )
    hora_final = models.TimeField(
        help_text='Hora de cierre de ventas'
    )
    permitir_ambos_turnos = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Configuración'
        verbose_name_plural = 'Configuración'

    def __str__(self):
        return f"Configuración del comedor ({self.apertura} - {self.cierre})"

    @classmethod
    def get(cls):
        """Devuelve la configuración activa. Siempre hay una sola."""
        return cls.objects.first()


class Feriado(models.Model):

    fecha = models.DateField(unique=True)
    detalle = models.CharField(max_length=100)

    class Meta:
        verbose_name = 'Feriado'
        verbose_name_plural = 'Feriados'
        ordering = ['fecha']

    def __str__(self):
        return f"{self.fecha} - {self.detalle}"


class Menu(models.Model):

    DIA_CHOICES = [
        (1, 'Lunes'),
        (2, 'Martes'),
        (3, 'Miércoles'),
        (4, 'Jueves'),
        (5, 'Viernes'),
    ]

    dia = models.IntegerField(choices=DIA_CHOICES, unique=True)
    menu_basico = models.TextField(blank=True)
    menu_veggie = models.TextField(blank=True)
    menu_sin_tacc = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Menú'
        verbose_name_plural = 'Menús'
        ordering = ['dia']

    def __str__(self):
        return f"{self.get_dia_display()}"


class Comentario(models.Model):

    usuario = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.CASCADE,
        related_name='comentarios'
    )
    comentario = models.TextField()
    fecha = models.DateField(auto_now_add=True)
    hora = models.TimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Comentario'
        verbose_name_plural = 'Comentarios'
        ordering = ['-fecha', '-hora']

    def __str__(self):
        return f"{self.usuario} - {self.fecha}"
