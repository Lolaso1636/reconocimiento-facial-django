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


class ServicioReconocimientoTest(TestCase):

  def setUp(self):
    from . import servicios
    servicios.invalidar_cache()

  def test_cache_se_invalida_al_guardar_persona(self):
    from . import servicios
    servicios.obtener_encodings_conocidos()
    self.assertIsNotNone(servicios._cache)
    Persona.objects.create(nombres='Ana', apellidos='Ruiz', documento='2')
    self.assertIsNone(servicios._cache)

  def test_cache_solo_incluye_personas_activas(self):
    from . import servicios
    activa = Persona.objects.create(nombres='Ana', apellidos='Ruiz', documento='1')
    inactiva = Persona.objects.create(nombres='Luis', apellidos='Mora', documento='2', activo=False)
    for p in (activa, inactiva):
      FotoEntrenamiento.objects.create(persona=p, imagen='x.jpg', encoding=[0.0] * 128, procesada=True)
    encodings, nombres, ids = servicios.obtener_encodings_conocidos()
    self.assertEqual(nombres, ['Ana Ruiz'])
    self.assertEqual(ids, [activa.id])

  def test_reconocer_rechaza_texto_invalido(self):
    from . import servicios
    with self.assertRaises(ValueError):
      servicios.reconocer('esto no es una imagen')

  def test_reconocer_imagen_sin_rostros(self):
    import base64
    import cv2
    import numpy as np
    from . import servicios
    _, jpg = cv2.imencode('.jpg', np.zeros((480, 640, 3), np.uint8))
    data_url = 'data:image/jpeg;base64,' + base64.b64encode(jpg.tobytes()).decode()
    self.assertEqual(servicios.reconocer(data_url), [])


class ComandosTest(TestCase):

  def test_crear_grupos(self):
    from io import StringIO
    from django.contrib.auth.models import Group
    from django.core.management import call_command
    call_command('crear_grupos', stdout=StringIO())
    call_command('crear_grupos', stdout=StringIO())  # se puede correr dos veces
    vigilante = Group.objects.get(name='Vigilante')
    self.assertEqual(
      set(vigilante.permissions.values_list('codename', flat=True)),
      {'view_persona', 'view_registroacceso', 'add_registroacceso'},
    )
    self.assertEqual(Group.objects.get(name='Administrador').permissions.count(), 12)


def crear_usuario(username, permisos=()):
  from django.contrib.auth.models import User, Permission
  usuario = User.objects.create_user(username, password='x')
  for codename in permisos:
    usuario.user_permissions.add(Permission.objects.get(codename=codename))
  return usuario


class HomeTest(TestCase):

  def test_home_redirige_al_login_sin_sesion(self):
    from django.urls import reverse
    respuesta = self.client.get(reverse('home'))
    self.assertRedirects(respuesta, f"{reverse('login')}?next=/")

  def test_home_sin_permisos_muestra_aviso(self):
    from django.urls import reverse
    self.client.force_login(crear_usuario('nuevo'))
    respuesta = self.client.get(reverse('home'))
    self.assertContains(respuesta, 'aún no tiene permisos asignados')
    self.assertNotContains(respuesta, 'Accesos de hoy')

  def test_home_con_permisos_muestra_estadisticas(self):
    from django.urls import reverse
    self.client.force_login(crear_usuario('vigilante', ['view_persona', 'view_registroacceso']))
    RegistroAcceso.objects.create(nombre_detectado='Unknown', distancia=0.7, reconocido=False)
    respuesta = self.client.get(reverse('home'))
    self.assertContains(respuesta, 'Accesos de hoy')
    self.assertEqual(respuesta.context['accesos_hoy'], 1)
    self.assertEqual(respuesta.context['desconocidos_hoy'], 1)
