import random
from datetime import date, timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group
from apps.accounts.models import CustomUser
from apps.comedor.models import Compra, LogCarga
from apps.core.models import Comentario


TIPOS = ['Estudiante', 'Estudiante', 'Estudiante', 'Docente', 'No Docente']
ESPECIALIDADES = ['Civil', 'Electrica', 'Industrial', 'Mecanica', 'Quimica', 'Sistemas', None]
MENUS = ['Basico', 'Basico', 'Basico', 'Veggie', 'Celiaco']
TURNOS = ['manana', 'manana', 'noche']
METODOS = ['Efectivo', 'Efectivo', 'Virtual', 'MP']

# Cantidad aproximada de compras por día de semana (lun=0 … vie=4)
DEMANDA = {0: (12, 20), 1: (22, 35), 2: (28, 42), 3: (20, 32), 4: (10, 18)}

NOMBRES = [
    ('Lucía', 'Fernández'), ('Mateo', 'González'), ('Valentina', 'López'),
    ('Santiago', 'Martínez'), ('Camila', 'Rodríguez'), ('Tomás', 'Pérez'),
    ('Sofía', 'García'), ('Nicolás', 'Sánchez'), ('Isabella', 'Ramírez'),
    ('Benjamín', 'Torres'), ('Martina', 'Flores'), ('Emilio', 'Rivera'),
    ('Valeria', 'Morales'), ('Agustín', 'Herrera'), ('Julieta', 'Jiménez'),
    ('Facundo', 'Díaz'), ('Catalina', 'Vargas'), ('Ignacio', 'Castro'),
    ('Abril', 'Ruiz'), ('Leandro', 'Ortega'), ('Florencia', 'Gutiérrez'),
    ('Marcos', 'Mendoza'), ('Antonella', 'Reyes'), ('Rodrigo', 'Cruz'),
    ('Milagros', 'Suárez'), ('Ezequiel', 'Ramos'), ('Pilar', 'Vega'),
    ('Mauricio', 'Ponce'), ('Aldana', 'Arias'), ('Sebastián', 'Bravo'),
]

COMENTARIOS_TEXTO = [
    'La comida estuvo muy buena hoy, especialmente el básico.',
    'El turno noche a veces se demora bastante. Sería bueno mejorar los tiempos.',
    'Sugiero incorporar más opciones vegetarianas.',
    '¿Es posible que el menú de la semana esté disponible antes del lunes?',
    'El personal es muy amable. Gracias por el buen servicio.',
]


class Command(BaseCommand):
    help = 'Genera datos de demostración para el dashboard (últimas 8 semanas)'

    def handle(self, *args, **kwargs):
        usuarios = self._crear_usuarios_demo()
        self._crear_compras_demo(usuarios)
        self._crear_cargas_demo(usuarios)
        self._crear_comentarios_demo(usuarios)
        self.stdout.write(self.style.SUCCESS('Seed demo completado.'))

    # ──────────────────────────────────────────────────────────────────────
    def _crear_usuarios_demo(self):
        grupo = Group.objects.get(name='comprador')
        creados = 0
        usuarios = []

        for i, (nombre, apellido) in enumerate(NOMBRES, start=1):
            documento = 80000000 + i
            tipo = random.choice(TIPOS)
            especialidad = random.choice(ESPECIALIDADES) if tipo == 'Estudiante' else None

            usuario, creado = CustomUser.objects.get_or_create(
                documento=documento,
                defaults={
                    'username': str(documento),
                    'first_name': nombre,
                    'last_name': apellido,
                    'email': f'demo{documento}@test.com',
                    'tipo': tipo,
                    'especialidad': especialidad,
                    'saldo': random.randint(500, 6000),
                    'es_becado': random.random() < 0.1,
                }
            )
            if creado:
                usuario.set_password('test1234')
                usuario.save()
                usuario.groups.add(grupo)
                creados += 1

            usuarios.append(usuario)

        self.stdout.write(f'  {creados} usuarios demo creados ({len(usuarios)} totales).')
        return usuarios

    # ──────────────────────────────────────────────────────────────────────
    def _crear_compras_demo(self, usuarios):
        hoy = date.today()
        lunes = hoy - timedelta(days=hoy.weekday())
        creadas = 0

        for semana in range(8):
            lunes_semana = lunes - timedelta(weeks=semana)

            for dia_offset in range(5):  # lun–vie
                dia = lunes_semana + timedelta(days=dia_offset)
                if dia >= hoy:
                    continue

                wd = dia.weekday()
                n_min, n_max = DEMANDA[wd]
                cantidad = random.randint(n_min, n_max)

                # Mezcla y recorta para no repetir usuario en el mismo día/turno
                candidatos = random.sample(usuarios, min(cantidad, len(usuarios)))

                for usuario in candidatos:
                    turno = random.choice(TURNOS)
                    ya_existe = Compra.objects.filter(
                        usuario=usuario, dia_comprado=dia, turno=turno
                    ).exists()
                    if ya_existe:
                        continue

                    precio = usuario.get_precio()
                    Compra.objects.create(
                        usuario=usuario,
                        dia_comprado=dia,
                        precio=precio,
                        turno=turno,
                        menu=random.choice(MENUS),
                        tipo=usuario.tipo,
                        retiro=random.random() < 0.85,
                    )
                    creadas += 1

        self.stdout.write(f'  {creadas} compras demo creadas.')

    # ──────────────────────────────────────────────────────────────────────
    def _crear_cargas_demo(self, usuarios):
        cajero = CustomUser.objects.filter(groups__name='cajero').first()
        hoy = date.today()
        lunes = hoy - timedelta(days=hoy.weekday())
        creadas = 0

        for semana in range(8):
            lunes_semana = lunes - timedelta(weeks=semana)

            for dia_offset in range(5):
                dia = lunes_semana + timedelta(days=dia_offset)
                if dia >= hoy:
                    continue

                n_cargas = random.randint(4, 12)
                for _ in range(n_cargas):
                    usuario = random.choice(usuarios)
                    monto = random.choice([500, 1000, 1500, 2000, 2500])
                    log = LogCarga.objects.create(
                        usuario=usuario,
                        vendedor=cajero,
                        monto=monto,
                        formato=random.choice(METODOS),
                    )
                    # Fijar fecha histórica (auto_now_add no permite asignarla en create)
                    LogCarga.objects.filter(pk=log.pk).update(fecha=dia)
                    creadas += 1

        self.stdout.write(f'  {creadas} cargas demo creadas.')

    # ──────────────────────────────────────────────────────────────────────
    def _crear_comentarios_demo(self, usuarios):
        for texto in COMENTARIOS_TEXTO:
            Comentario.objects.get_or_create(
                comentario=texto,
                defaults={
                    'usuario': random.choice(usuarios),
                    'leido': False,
                }
            )
        self.stdout.write(f'  {len(COMENTARIOS_TEXTO)} comentarios demo creados.')
