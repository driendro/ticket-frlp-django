# apps/admin_panel/urls.py
from django.urls import path
from . import views

app_name = 'admin_panel'

urlpatterns = [
    path('', views.IndexView.as_view(), name='index'),
    path('cargar-saldo/', views.CargarSaldoView.as_view(), name='cargar_saldo'),
    path('nuevo-usuario/', views.CrearUsuarioView.as_view(), name='crear_usuario'),
    path('modificar-usuario/<int:pk>/',
         views.ModificarUsuarioView.as_view(), name='modificar_usuario'),
    path('historial/', views.HistorialCargasView.as_view(), name='historial'),
    path('compras/<int:pk>/',
         views.VerComprasUsuarioView.as_view(), name='ver_compras'),
    path('compras/<int:usuario_pk>/devolver/<int:compra_pk>/',
         views.DevolverCompraAdminView.as_view(), name='devolver_compra'),
    path('repartidor/', views.RepartidorView.as_view(), name='repartidor'),
    path('repartidor/entregar/', views.EntregarViandaView.as_view(), name='entregar'),

    # Administrador
    path('configuracion/', views.ConfiguracionView.as_view(), name='configuracion'),
    path('precios/', views.PreciosView.as_view(), name='precios'),
    path('feriados/', views.FeriadosView.as_view(), name='feriados'),
    path('feriados/agregar/', views.AgregarFeriadoView.as_view(),
         name='agregar_feriado'),
    path('feriados/eliminar/<int:pk>/',
         views.EliminarFeriadoView.as_view(), name='eliminar_feriado'),
    path('menu/', views.MenuAdminView.as_view(), name='menu'),
    path('csv/', views.CargaCSVView.as_view(), name='carga_csv'),
    path('csv/confirmar/', views.ConfirmarCSVView.as_view(), name='confirmar_csv'),
    path('excel/', views.DescargarExcelView.as_view(), name='excel'),
    path('informe/', views.CierreCajaDiarioView.as_view(), name='informe'),
    path('informe/semana/', views.CierreCajaSemanalView.as_view(),
         name='informe_semana'),
    path('informe/pedidos/', views.ResumenPedidosSemanaView.as_view(),
         name='informe_pedidos'),
]
