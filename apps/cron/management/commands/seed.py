# apps/cron/management/commands/seed.py
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group


class Command(BaseCommand):
    help = 'Carga datos de prueba para desarrollo'

    def handle(self, *args, **kwargs):
        self._crear_grupos()
        self._crear_precios()
        self._crear_configuracion()
        self._crear_menu()
        self._crear_usuarios()
        self.stdout.write(self.style.SUCCESS('Seed completado.'))

    def _crear_grupos(self):
        for nombre in ['cajero', 'administrador', 'repartidor']:
            Group.objects.get_or_create(name=nombre)
        self.stdout.write('  Grupos creados.')

    def _crear_precios(self):
        from apps.core.models import Precio
        precios = [
            ('Estudiante', 500),
            ('Becado', 250),
            ('Docente', 800),
            ('No Docente', 800),
        ]
        for tipo, costo in precios:
            Precio.objects.get_or_create(
                tipo_user=tipo,
                defaults={'costo': costo}
            )
        self.stdout.write('  Precios creados.')

    def _crear_configuracion(self):
        from apps.core.models import Configuracion
        from datetime import date, time

        if not Configuracion.objects.exists():
            Configuracion.objects.create(
                apertura=date(2026, 3, 1),
                cierre=date(2026, 11, 30),
                vacaciones_inicio=date(2026, 7, 14),
                vacaciones_fin=date(2026, 7, 25),
                dia_inicial=1,
                dia_final=5,
                hora_final=time(4, 0, 0),
                permitir_ambos_turnos=False,
            )
            self.stdout.write('  Configuración creada.')
        else:
            self.stdout.write('  Configuración ya existe, salteando.')

    def _crear_menu(self):
        from apps.core.models import Menu
        dias = [
            (1, 'Milanesa con puré', 'Tarta de verduras', 'Arroz con pollo'),
            (2, 'Guiso de lentejas', 'Pasta con salsa', 'Pollo al horno'),
            (3, 'Fideos con tuco', 'Ensalada completa', 'Milanesa al horno'),
            (4, 'Locro', 'Omelette de verduras', 'Bife con papas'),
            (5, 'Pizza', 'Empanadas de verdura', 'Pollo grillado'),
        ]
        for dia, basico, veggie, sin_tacc in dias:
            Menu.objects.get_or_create(
                dia=dia,
                defaults={
                    'menu_basico': basico,
                    'menu_veggie': veggie,
                    'menu_sin_tacc': sin_tacc,
                }
            )
        self.stdout.write('  Menú creado.')

    def _crear_usuarios(self):
        from apps.accounts.models import CustomUser
        from django.contrib.auth.models import Group

        usuarios = [
            {
                'documento': 11111111,
                'username': '11111111',
                'first_name': 'Juan',
                'last_name': 'Estudiante',
                'email': 'estudiante@test.com',
                'tipo': 'Estudiante',
                'especialidad': 'Civil',
                'saldo': 2000,
                'es_becado': False,
                'password': 'test1234',
                'grupo': None,
                'is_staff': False,
            },
            {
                'documento': 22222222,
                'username': '22222222',
                'first_name': 'María',
                'last_name': 'Becada',
                'email': 'becado@test.com',
                'tipo': 'Estudiante',
                'especialidad': 'Sistemas',
                'saldo': 500,
                'es_becado': True,
                'password': 'test1234',
                'grupo': None,
                'is_staff': False,
            },
            {
                'documento': 33333333,
                'username': '33333333',
                'first_name': 'Carlos',
                'last_name': 'Docente',
                'email': 'docente@test.com',
                'tipo': 'Docente',
                'especialidad': None,
                'saldo': 3000,
                'es_becado': False,
                'password': 'test1234',
                'grupo': None,
                'is_staff': False,
            },
            {
                'documento': 44444444,
                'username': '44444444',
                'first_name': 'Ana',
                'last_name': 'NoDocente',
                'email': 'nodocente@test.com',
                'tipo': 'No Docente',
                'especialidad': None,
                'saldo': 1500,
                'es_becado': False,
                'password': 'test1234',
                'grupo': None,
                'is_staff': False,
            },
            {
                'documento': 55555555,
                'username': '55555555',
                'first_name': 'Pedro',
                'last_name': 'Cajero',
                'email': 'cajero@test.com',
                'tipo': 'No Docente',
                'especialidad': None,
                'saldo': 0,
                'es_becado': False,
                'password': 'test1234',
                'grupo': 'cajero',
                'is_staff': True,
            },
            {
                'documento': 66666666,
                'username': '66666666',
                'first_name': 'Laura',
                'last_name': 'Administrador',
                'email': 'admin@test.com',
                'tipo': 'No Docente',
                'especialidad': None,
                'saldo': 0,
                'es_becado': False,
                'password': 'test1234',
                'grupo': 'administrador',
                'is_staff': True,
            },
            {
                'documento': 77777777,
                'username': '77777777',
                'first_name': 'Roberto',
                'last_name': 'Repartidor',
                'email': 'repartidor@test.com',
                'tipo': 'No Docente',
                'especialidad': None,
                'saldo': 0,
                'es_becado': False,
                'password': 'test1234',
                'grupo': 'repartidor',
                'is_staff': True,
            },
        ]

        for datos in usuarios:
            grupo_nombre = datos.pop('grupo')
            password = datos.pop('password')
            is_staff = datos.pop('is_staff')

            usuario, creado = CustomUser.objects.get_or_create(
                documento=datos['documento'],
                defaults=datos
            )

            if creado:
                usuario.set_password(password)
                usuario.is_staff = is_staff
                usuario.save()

                if grupo_nombre:
                    grupo = Group.objects.get(name=grupo_nombre)
                    usuario.groups.add(grupo)

                self.stdout.write(
                    f'  Usuario {usuario.nombre_completo} '
                    f'({datos["documento"]}) creado.'
                )
            else:
                self.stdout.write(
                    f'  Usuario {datos["documento"]} ya existe, salteando.'
                )
