from django.db import models


class Persona(models.Model):
  '''
  Modelo que representa una persona que el sistema puede reconocer
  '''
  ROL_CHOICES = [
    ('ESTUDIANTE', 'Estudiante'),
    ('DOCENTE', 'Docente'),
    ('ADMINISTRATIVO', 'Administrativo'),
    ('VISITANTE', 'Visitante'),
  ]

  nombres = models.CharField(max_length=100)
  apellidos = models.CharField(max_length=100)
  documento = models.CharField(max_length=20, unique=True)
  rol = models.CharField(
    max_length=14,
    choices=ROL_CHOICES,
    default='ESTUDIANTE'
  )
  programa = models.CharField(max_length=150, blank=True)
  activo = models.BooleanField(default=True)
  foto_perfil = models.ImageField(upload_to='personas/', blank=True, null=True)
  fecha_registro = models.DateTimeField(auto_now_add=True)

  class Meta:
    ordering = ['nombres', 'apellidos']

  def __str__(self):
    return f"{self.nombre_completo} ({self.documento})"

  @property
  def nombre_completo(self):
    return f"{self.nombres} {self.apellidos}".strip()


class FotoEntrenamiento(models.Model):
  '''
  Foto de una persona usada para calcular su encoding facial (128 valores)
  '''
  persona = models.ForeignKey(
    Persona,
    on_delete=models.CASCADE,
    related_name="fotos"
  )
  imagen = models.ImageField(upload_to='entrenamiento/')
  encoding = models.JSONField(null=True, blank=True)
  procesada = models.BooleanField(default=False)
  fecha = models.DateTimeField(auto_now_add=True)

  def __str__(self):
    return f"Foto {self.id} de {self.persona.nombre_completo}"


class RegistroAcceso(models.Model):
  '''
  Registro de cada detección hecha por la cámara (reconocida o desconocida)
  '''
  persona = models.ForeignKey(
    Persona,
    on_delete=models.SET_NULL,
    null=True,
    blank=True,
    related_name="accesos"
  )
  nombre_detectado = models.CharField(max_length=200)
  distancia = models.FloatField()
  reconocido = models.BooleanField(default=False)
  fecha_hora = models.DateTimeField(auto_now_add=True)

  class Meta:
    ordering = ['-fecha_hora']

  def __str__(self):
    return f"{self.nombre_detectado} - {self.fecha_hora:%d/%m/%Y %H:%M:%S}"
