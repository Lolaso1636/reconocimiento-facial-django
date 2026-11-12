from django.test import TestCase

from .models import Persona, FotoEntrenamiento, RegistroAcceso


class ModelosTest(TestCase):

  def setUp(self):
    self.persona = Persona.objects.create(
      nombres='Isabella',
      apellidos='Ardila',
      documento='1000000001',
      rol='ESTUDIANTE',
      programa='Ingeniería de Sistemas',
    )

  def test_crear_persona(self):
    self.assertEqual(self.persona.nombre_completo, 'Isabella Ardila')
    self.assertEqual(str(self.persona), 'Isabella Ardila (1000000001)')
    self.assertTrue(self.persona.activo)

  def test_crear_foto_entrenamiento(self):
    foto = FotoEntrenamiento.objects.create(persona=self.persona, imagen='entrenamiento/x.jpg')
    self.assertFalse(foto.procesada)
    self.assertIsNone(foto.encoding)
    self.assertEqual(self.persona.fotos.count(), 1)

  def test_registro_acceso_queda_sin_persona_al_eliminarla(self):
    RegistroAcceso.objects.create(
      persona=self.persona, nombre_detectado='Isabella Ardila', distancia=0.3, reconocido=True
    )
    self.persona.delete()
    registro = RegistroAcceso.objects.get()
    self.assertIsNone(registro.persona)
    self.assertEqual(registro.nombre_detectado, 'Isabella Ardila')
