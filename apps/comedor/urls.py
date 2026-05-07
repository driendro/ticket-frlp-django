from django.urls import path
from . import views

app_name = 'comedor'

urlpatterns = [
    path('', views.IndexView.as_view(), name='index'),
    path('devolver/', views.DevolverCompraView.as_view(), name='devolver'),
    path('movimientos/', views.MovimientosView.as_view(), name='movimientos'),
    path('menu/', views.MenuView.as_view(), name='menu'),
    path('faq/', views.FaqView.as_view(), name='faq'),
    path('contacto/', views.ContactoView.as_view(), name='contacto'),
]