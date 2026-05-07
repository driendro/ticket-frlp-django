# apps/pagos/models.py
from django.db import models
from django.conf import settings


class CompraPendiente(models.Model):

    MP_ESTADO_CHOICES = [
        ('pending', 'Pendiente'),
        ('pasarela', 'En pasarela'),
        ('approved', 'Aprobado'),
        ('rejected', 'Rechazado'),
        ('cancelled', 'Cancelado'),
        ('in_process', 'En proceso'),
        ('expired_by_date_cutoff', 'Expirado por fecha'),
        ('expired_by_cronjob', 'Expirado por cronjob'),
        ('cancelled_by_user', 'Cancelado por usuario'),
    ]

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='compras_pendientes'
    )
    external_reference = models.CharField(max_length=255, unique=True)
    datos = models.TextField()
    total = models.DecimalField(max_digits=10, decimal_places=2)
    procesada = models.BooleanField(default=False)
    mp_estado = models.CharField(
        max_length=30,
        choices=MP_ESTADO_CHOICES,
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Compra Pendiente'
        verbose_name_plural = 'Compras Pendientes'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.usuario} - {self.external_reference} - {self.mp_estado}"

    @classmethod
    def get_pasarela_activa(cls, usuario):
        """Retorna la compra en pasarela activa del usuario si existe."""
        return cls.objects.filter(
            usuario=usuario,
            mp_estado='pasarela',
            procesada=False
        ).first()


class CargaVirtual(models.Model):

    ESTADO_CHOICES = [
        ('revision', 'En revisión'),
        ('aprobado', 'Aprobado'),
        ('rechazado', 'Rechazado'),
    ]

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='cargas_virtuales'
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    estado = models.CharField(
        max_length=20, choices=ESTADO_CHOICES, default='revision')
    confirmacion_timestamp = models.DateTimeField(null=True, blank=True)
    confirmacion_vendedor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cargas_confirmadas'
    )

    class Meta:
        verbose_name = 'Carga Virtual'
        verbose_name_plural = 'Cargas Virtuales'
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.usuario} - ${self.monto} - {self.estado}"


class LinkPago(models.Model):

    TIPO_CHOICES = [
        ('Estudiante', 'Estudiante'),
        ('Docente', 'Docente'),
        ('No Docente', 'No Docente'),
    ]

    valor = models.DecimalField(max_digits=10, decimal_places=2)
    link = models.URLField(max_length=255)
    tipo_user = models.CharField(max_length=20, choices=TIPO_CHOICES)

    class Meta:
        verbose_name = 'Link de Pago'
        verbose_name_plural = 'Links de Pago'

    def __str__(self):
        return f"{self.tipo_user} - ${self.valor}"
