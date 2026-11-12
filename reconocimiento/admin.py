from django.contrib import admin
from .models import Persona, FotoEntrenamiento, RegistroAcceso


class FotoEntrenamientoInline(admin.TabularInline):
  model = FotoEntrenamiento
  extra = 0
  fields = ('imagen', 'procesada', 'fecha')
  readonly_fields = ('procesada', 'fecha')


@admin.register(Persona)
class PersonaAdmin(admin.ModelAdmin):
  list_display = ('nombres', 'apellidos', 'documento', 'rol', 'programa', 'activo', 'fecha_registro')
  list_filter = ('rol', 'activo')
  search_fields = ('nombres', 'apellidos', 'documento', 'programa')
  inlines = [FotoEntrenamientoInline]


@admin.register(FotoEntrenamiento)
class FotoEntrenamientoAdmin(admin.ModelAdmin):
  list_display = ('id', 'persona', 'procesada', 'fecha')
  list_filter = ('procesada',)
  search_fields = ('persona__nombres', 'persona__apellidos', 'persona__documento')
  exclude = ('encoding',)


@admin.register(RegistroAcceso)
class RegistroAccesoAdmin(admin.ModelAdmin):
  list_display = ('nombre_detectado', 'persona', 'reconocido', 'distancia', 'fecha_hora')
  list_filter = ('reconocido', 'fecha_hora')
  search_fields = ('nombre_detectado', 'persona__nombres', 'persona__apellidos', 'persona__documento')
