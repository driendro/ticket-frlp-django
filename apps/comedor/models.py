# apps/comedor/models.py
from django.db import models
from django.conf import settings


class Compra(models.Model):

    TURNO_CHOICES = [
        ('manana', 'Mediodía'),
        ('noche', 'Noche'),
    ]

    MENU_CHOICES = [
        ('Basico', 'Básico'),
        ('Veggie', 'Vegetariano'),
        ('Celiaco', 'Sin TACC'),
    ]

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='compras'
    )
    fecha = models.DateField(auto_now_add=True)
    hora = models.TimeField(auto_now_add=True)
    dia_comprado = models.DateField()
    precio = models.DecimalField(max_digits=10, decimal_places=2)
    turno = models.CharField(max_length=10, choices=TURNO_CHOICES)
    menu = models.CharField(max_length=10, choices=MENU_CHOICES)
    tipo = models.CharField(max_length=20, blank=True)
    transaccion = models.ForeignKey(
        'Transaccion',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='compras'
    )
    external_reference = models.CharField(
        max_length=255, null=True, blank=True)
    retiro = models.BooleanField(default=False)
    repartidor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='entregas'
    )

    class Meta:
        verbose_name = 'Compra'
        verbose_name_plural = 'Compras'
        ordering = ['-dia_comprado']

    def __str__(self):
        return f"{self.usuario} - {self.dia_comprado} - {self.get_turno_display()}"


class Transaccion(models.Model):

    TIPO_CHOICES = [
        ('Compra con saldo', 'Compra con saldo'),
        ('Compra por Mercado Pago', 'Compra por Mercado Pago'),
        ('Carga de Saldo', 'Carga de Saldo'),
        ('Devolucion', 'Devolución'),
        ('Reintegro', 'Reintegro'),
    ]

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='transacciones'
    )
    fecha = models.DateField(auto_now_add=True)
    hora = models.TimeField(auto_now_add=True)
    transaccion = models.CharField(max_length=30, choices=TIPO_CHOICES)
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    saldo = models.DecimalField(max_digits=10, decimal_places=2)
    external_reference = models.CharField(
        max_length=255, null=True, blank=True)

    class Meta:
        verbose_name = 'Transacción'
        verbose_name_plural = 'Transacciones'
        ordering = ['-fecha', '-hora']

    def __str__(self):
        return f"{self.usuario} - {self.transaccion} - ${self.monto}"


class LogCompra(models.Model):

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='log_compras'
    )
    fecha = models.DateField(auto_now_add=True)
    hora = models.TimeField(auto_now_add=True)
    dia_comprado = models.DateField()
    precio = models.DecimalField(max_digits=10, decimal_places=2)
    turno = models.CharField(max_length=10)
    menu = models.CharField(max_length=10)
    tipo = models.CharField(max_length=20, blank=True)
    transaccion_tipo = models.CharField(max_length=30, blank=True)
    transaccion = models.ForeignKey(
        Transaccion,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='logs'
    )
    external_reference = models.CharField(
        max_length=255, null=True, blank=True)

    class Meta:
        verbose_name = 'Log de Compra'
        verbose_name_plural = 'Logs de Compras'
        ordering = ['-fecha', '-hora']

    def __str__(self):
        return f"{self.usuario} - {self.dia_comprado}"


class LogCarga(models.Model):

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='log_cargas'
    )
    vendedor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cargas_realizadas'
    )
    fecha = models.DateField(auto_now_add=True)
    hora = models.TimeField(auto_now_add=True)
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    formato = models.CharField(max_length=20, default='Efectivo')
    transaccion = models.ForeignKey(
        Transaccion,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cargas'
    )

    class Meta:
        verbose_name = 'Log de Carga'
        verbose_name_plural = 'Logs de Cargas'
        ordering = ['-fecha', '-hora']

    def __str__(self):
        return f"{self.usuario} - ${self.monto} - {self.formato}"
