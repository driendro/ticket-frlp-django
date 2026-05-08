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
]
