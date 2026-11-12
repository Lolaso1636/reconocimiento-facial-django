from django.urls import path
from . import views

urlpatterns = [
  path('', views.home, name='home'),
  path('personas/', views.personas, name='personas'),
  path('personas/nueva/', views.crear_persona, name='crear_persona'),
  path('personas/<int:id>/', views.detalle_persona, name='detalle_persona'),
  path('personas/<int:id>/editar/', views.editar_persona, name='editar_persona'),
  path('personas/<int:id>/eliminar/', views.eliminar_persona, name='eliminar_persona'),
  path('personas/<int:id>/fotos/agregar/', views.agregar_foto, name='agregar_foto'),
  path('fotos/<int:id>/eliminar/', views.eliminar_foto, name='eliminar_foto'),
  path('entrenar/', views.entrenar, name='entrenar'),
  path('camara/', views.camara, name='camara'),
  path('api/reconocer/', views.api_reconocer, name='api_reconocer'),
  path('historial/', views.historial, name='historial'),
]
