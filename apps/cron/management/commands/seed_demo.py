import random
from datetime import date, timedelta, time
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group
from apps.accounts.models import CustomUser
from apps.comedor.models import Compra, LogCarga
from apps.core.models import Comentario


# Variación estacional relativa al pico (oct/abr = 1.0)
SEASONAL = {
    1: 0.12, 2: 0.65, 3: 0.95, 4: 1.00,
    5: 0.90, 6: 0.80, 7: 0.18, 8: 0.78,
    9: 0.92, 10: 1.00, 11: 0.75, 12: 0.40,
}

# Demanda base lun–vie en pico (min, max)
DEMANDA_BASE = {0: (12, 20), 1: (22, 35), 2: (28, 42), 3: (20, 32), 4: (10, 18)}

MENUS  = ['Basico', 'Basico', 'Basico', 'Veggie', 'Celiaco']
TURNOS = ['manana', 'manana', 'noche']
METODOS = ['Efectivo', 'Efectivo', 'Virtual', 'MP']

# Distribución de minutos dentro de cada hora de retiro
# Turno mañana: 11:30–13:30  |  Turno noche: 19:30–21:30
HORAS_MANANA = (
    [(11, m) for m in range(30, 60)] * 1 +
    [(12, m) for m in range(0, 60)]  * 3 +
    [(13, m) for m in range(0, 30)]  * 2
)
HORAS_NOCHE = (
    [(19, m) for m in range(30, 60)] * 1 +
    [(20, m) for m in range(0, 60)]  * 3 +
    [(21, m) for m in range(0, 30)]  * 2
)

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
    help = 'Genera datos de demostración para el dashboard (52 semanas con estacionalidad)'

    def handle(self, *args, **kwargs):
        usuarios = self._crear_usuarios_demo()
        self._limpiar_compras_demo(usuarios)
        self._crear_compras_demo(usuarios)
        self._crear_cargas_demo(usuarios)
        self._crear_comentarios_demo(usuarios)
        self.stdout.write(self.style.SUCCESS('Seed demo completado.'))

    def _crear_usuarios_demo(self):
        grupo = Group.objects.get(name='comprador')
        creados, usuarios = 0, []
        for i, (nombre, apellido) in enumerate(NOMBRES, start=1):
            documento = 80000000 + i
            tipo = random.choice(['Estudiante', 'Estudiante', 'Estudiante', 'Docente', 'No Docente'])
            usuario, creado = CustomUser.objects.get_or_create(
                documento=documento,
                defaults={
                    'username': str(documento),
                    'first_name': nombre,
                    'last_name': apellido,
                    'email': f'demo{documento}@test.com',
                    'tipo': tipo,
                    'especialidad': random.choice(['Civil','Electrica','Sistemas',None]) if tipo == 'Estudiante' else None,
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

    def _limpiar_compras_demo(self, usuarios):
        ids = [u.id for u in usuarios]
        eliminadas, _ = Compra.objects.filter(usuario_id__in=ids).delete()
        LogCarga.objects.filter(usuario_id__in=ids).delete()
        self.stdout.write(f'  {eliminadas} compras previas eliminadas.')

    def _crear_compras_demo(self, usuarios):
        hoy = date.today()
        lunes_actual = hoy - timedelta(days=hoy.weekday())
        creadas = 0

        for semana in range(52):
            lunes = lunes_actual - timedelta(weeks=semana)

            for dia_offset in range(5):
                dia = lunes + timedelta(days=dia_offset)
                if dia >= hoy:
                    continue

                factor = SEASONAL.get(dia.month, 1.0)
                wd = dia.weekday()
                n_min, n_max = DEMANDA_BASE[wd]
                cantidad = int(random.randint(n_min, n_max) * factor)
                if cantidad == 0:
                    continue

                candidatos = random.sample(usuarios, min(cantidad, len(usuarios)))
                for usuario in candidatos:
                    turno = random.choice(TURNOS)
                    hora_pool = HORAS_MANANA if turno == 'manana' else HORAS_NOCHE
                    es_retiro = random.random() < 0.85
                    hora_h, hora_m = random.choice(hora_pool)

                    Compra.objects.create(
                        usuario=usuario,
                        dia_comprado=dia,
                        precio=usuario.get_precio(),
                        turno=turno,
                        menu=random.choice(MENUS),
                        tipo=usuario.tipo,
                        retiro=es_retiro,
                        hora_retiro=time(hora_h, hora_m) if es_retiro else None,
                    )
                    creadas += 1

        self.stdout.write(f'  {creadas} compras demo creadas.')

    def _crear_cargas_demo(self, usuarios):
        cajero = CustomUser.objects.filter(groups__name='cajero').first()
        hoy = date.today()
        lunes_actual = hoy - timedelta(days=hoy.weekday())
        creadas = 0

        for semana in range(52):
            lunes = lunes_actual - timedelta(weeks=semana)
            for dia_offset in range(5):
                dia = lunes + timedelta(days=dia_offset)
                if dia >= hoy:
                    continue
                factor = SEASONAL.get(dia.month, 1.0)
                for _ in range(int(random.randint(4, 12) * factor)):
                    log = LogCarga.objects.create(
                        usuario=random.choice(usuarios),
                        vendedor=cajero,
                        monto=random.choice([500, 1000, 1500, 2000, 2500]),
                        formato=random.choice(METODOS),
                    )
                    LogCarga.objects.filter(pk=log.pk).update(fecha=dia)
                    creadas += 1

        self.stdout.write(f'  {creadas} cargas demo creadas.')

    def _crear_comentarios_demo(self, usuarios):
        for texto in COMENTARIOS_TEXTO:
            Comentario.objects.get_or_create(
                comentario=texto,
                defaults={'usuario': random.choice(usuarios), 'leido': False}
            )
        self.stdout.write(f'  {len(COMENTARIOS_TEXTO)} comentarios demo creados.')
