# Ticket Web - UTN FRLP

Sistema de gestión del Comedor Universitario de la UTN Facultad Regional La Plata.

> 🚧 Este repositorio es una reescritura en Django del sistema original desarrollado en CodeIgniter 3 ([ver repositorio original](URL_DEL_REPO_CI3)).

## Funcionalidades

- Compra y devolución de viandas semanales
- Integración con Mercado Pago (pago parcial con saldo de cuenta)
- Gestión de saldo por usuario
- Panel de administración para vendedores, administradores y repartidores
- Sistema de feriados y configuración de períodos académicos
- Reportes en Excel y PDF
- Autenticación por número de documento
- Recuperación de contraseña por email

## Stack

- **Backend:** Python 3.x / Django
- **Base de datos:** PostgreSQL (producción) / SQLite (desarrollo)
- **Frontend:** Bootstrap 5
- **Pagos:** Mercado Pago SDK Python
- **Email:** Django mail / Gmail SMTP
- **Reportes:** openpyxl (Excel) / WeasyPrint (PDF)

## Instalación local

### Requisitos

- Python 3.11+
- pip

### Pasos

```bash
# Clonar el repositorio
git clone https://github.com/tu_usuario/ticket-frlp-django
cd ticket-frlp-django

# Crear entorno virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
.\venv\Scripts\activate   # Windows

# Instalar dependencias
pip install -r requirements.txt

# Configurar variables de entorno
cp .env.example .env
# Editar .env con tus valores

# Correr migraciones
python manage.py migrate

# Cargar datos iniciales
python manage.py loaddata fixtures/inicial.json

# Crear superusuario
python manage.py createsuperuser

# Levantar servidor
python manage.py runserver
```

## Variables de entorno

Creá un archivo `.env` en la raíz del proyecto basándote en `.env.example`:

```bash
SECRET_KEY=tu_secret_key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Solo producción
DATABASE_URL=postgresql://user:pass@localhost/ticket_frlp

# Email
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=tu_correo@gmail.com
EMAIL_HOST_PASSWORD=tu_app_password

# Mercado Pago
MP_ACCESS_TOKEN=
MP_PUBLIC_KEY=
MP_WEBHOOK_SECRET=
```

## Estructura del proyecto

```
ticket-frlp-django/
├── config/                  # Settings, URLs, WSGI
├── apps/
│   ├── accounts/            # Usuarios, autenticación
│   ├── comedor/             # Compra, devolución, menú
│   ├── admin_panel/         # Vendedor, administrador, repartidor
│   ├── pagos/               # Mercado Pago, webhook
│   ├── cron/                # Tareas programadas
│   └── core/                # Configuración, feriados, emails
├── templates/
├── static/
├── requirements.txt
└── manage.py
```

## Roadmap

- [x] Setup del proyecto
- [x] Autenticación por documento
- [x] Modelos base (Configuración, Feriados, Precios, Menú)
- [ ] App comedor (compra y devolución de viandas)
- [ ] Integración Mercado Pago
- [ ] Panel de administración
- [ ] Reportes Excel y PDF
- [ ] Tareas programadas
- [ ] Migración de datos desde MySQL

## Autor

Desarrollado por **RONCONI, Jorge** - UTN FRLP  
Secretaría de Asuntos Universitarios
