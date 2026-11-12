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


import shutil
import tempfile
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse

MEDIA_TEMPORAL = tempfile.mkdtemp()


def imagen_subida(nombre='foto.jpg'):
  import cv2
  import numpy as np
  _, jpg = cv2.imencode('.jpg', np.zeros((20, 20, 3), np.uint8))
  return SimpleUploadedFile(nombre, jpg.tobytes(), content_type='image/jpeg')


@override_settings(MEDIA_ROOT=MEDIA_TEMPORAL)
class PersonasVistasTest(TestCase):

  @classmethod
  def tearDownClass(cls):
    super().tearDownClass()
    shutil.rmtree(MEDIA_TEMPORAL, ignore_errors=True)

  def setUp(self):
    self.persona = Persona.objects.create(nombres='Isabella', apellidos='Ardila', documento='100')
    self.admin = crear_usuario('admin', [
      'view_persona', 'add_persona', 'change_persona', 'delete_persona',
    ])

  def test_vistas_protegidas_redirigen_al_login(self):
    urls = [
      reverse('personas'),
      reverse('detalle_persona', args=[self.persona.id]),
      reverse('crear_persona'),
      reverse('editar_persona', args=[self.persona.id]),
    ]
    for url in urls:
      respuesta = self.client.get(url)
      self.assertEqual(respuesta.status_code, 302, url)
      self.assertTrue(respuesta.url.startswith(reverse('login')), url)

  def test_usuario_sin_permiso_recibe_403(self):
    self.client.force_login(crear_usuario('sinpermisos'))
    self.assertEqual(self.client.get(reverse('personas')).status_code, 403)
    self.assertEqual(self.client.get(reverse('crear_persona')).status_code, 403)
    respuesta = self.client.post(reverse('eliminar_persona', args=[self.persona.id]))
    self.assertEqual(respuesta.status_code, 403)
    self.assertTrue(Persona.objects.filter(id=self.persona.id).exists())

  def test_listar_y_buscar(self):
    Persona.objects.create(nombres='Juan', apellidos='Melo', documento='200')
    self.client.force_login(self.admin)
    respuesta = self.client.get(reverse('personas'), {'q': 'ardila'})
    self.assertEqual(list(respuesta.context['personas']), [self.persona])

  def test_detalle_inexistente_da_404(self):
    self.client.force_login(self.admin)
    self.assertEqual(self.client.get(reverse('detalle_persona', args=[999])).status_code, 404)

  @mock.patch('reconocimiento.views.servicios.generar_encoding', return_value=(True, 'ok'))
  def test_crear_persona_con_varias_fotos(self, generar):
    self.client.force_login(self.admin)
    respuesta = self.client.post(reverse('crear_persona'), {
      'nombres': 'Juan', 'apellidos': 'Melo', 'documento': '300',
      'rol': 'DOCENTE', 'programa': '', 'activo': 'on',
      'fotos': [imagen_subida('a.jpg'), imagen_subida('b.jpg')],
    })
    persona = Persona.objects.get(documento='300')
    self.assertRedirects(respuesta, reverse('detalle_persona', args=[persona.id]))
    self.assertEqual(persona.fotos.count(), 2)
    self.assertEqual(generar.call_count, 2)

  def test_crear_persona_documento_repetido(self):
    self.client.force_login(self.admin)
    respuesta = self.client.post(reverse('crear_persona'), {
      'nombres': 'Otra', 'apellidos': 'Persona', 'documento': '100', 'rol': 'ESTUDIANTE',
    })
    self.assertContains(respuesta, 'Ya existe una persona con ese documento.')

  def test_editar_persona(self):
    self.client.force_login(self.admin)
    self.client.post(reverse('editar_persona', args=[self.persona.id]), {
      'nombres': 'Isabella', 'apellidos': 'Ardila', 'documento': '100',
      'rol': 'VISITANTE', 'programa': 'Derecho',
    })
    self.persona.refresh_from_db()
    self.assertEqual(self.persona.rol, 'VISITANTE')
    self.assertFalse(self.persona.activo)  # checkbox sin marcar

  def test_eliminar_persona_solo_por_post(self):
    self.client.force_login(self.admin)
    url = reverse('eliminar_persona', args=[self.persona.id])
    self.assertEqual(self.client.get(url).status_code, 405)
    self.client.post(url)
    self.assertFalse(Persona.objects.filter(id=self.persona.id).exists())

  @mock.patch('reconocimiento.views.servicios.generar_encoding', return_value=(False, 'No se detectó ningún rostro en la foto.'))
  def test_agregar_y_eliminar_foto(self, generar):
    self.client.force_login(self.admin)
    respuesta = self.client.post(reverse('agregar_foto', args=[self.persona.id]), {'fotos': [imagen_subida()]}, follow=True)
    self.assertContains(respuesta, 'No se detectó ningún rostro')
    foto = self.persona.fotos.get()
    self.client.post(reverse('eliminar_foto', args=[foto.id]))
    self.assertEqual(self.persona.fotos.count(), 0)

  def test_entrenar_solo_staff(self):
    self.client.force_login(self.admin)  # tiene permisos pero no es staff
    respuesta = self.client.post(reverse('entrenar'))
    self.assertEqual(respuesta.status_code, 302)
    self.assertTrue(respuesta.url.startswith(reverse('login')))

  @mock.patch('reconocimiento.views.servicios.generar_encoding', return_value=(True, 'ok'))
  def test_entrenar_regenera_todas_las_fotos(self, generar):
    FotoEntrenamiento.objects.create(persona=self.persona, imagen='a.jpg')
    FotoEntrenamiento.objects.create(persona=self.persona, imagen='b.jpg')
    self.admin.is_staff = True
    self.admin.save()
    self.client.force_login(self.admin)
    respuesta = self.client.post(reverse('entrenar'), follow=True)
    self.assertEqual(generar.call_count, 2)
    self.assertContains(respuesta, '2 foto(s) procesada(s), 0 con error')


class ApiReconocerTest(TestCase):

  def setUp(self):
    self.persona = Persona.objects.create(nombres='Isabella', apellidos='Ardila', documento='100')
    self.vigilante = crear_usuario('vigilante', ['add_registroacceso'])
    self.url = reverse('api_reconocer')

  def post_json(self, cuerpo, **extra):
    import json
    return self.client.post(self.url, json.dumps(cuerpo), content_type='application/json', **extra)

  def rostro(self, name, persona_id, distancia=0.3):
    return {'name': name, 'box': [60, 472, 368, 162], 'distancia': distancia, 'persona_id': persona_id}

  def test_camara_redirige_al_login_y_da_403_sin_permiso(self):
    respuesta = self.client.get(reverse('camara'))
    self.assertTrue(respuesta.url.startswith(reverse('login')))
    self.client.force_login(crear_usuario('sinpermisos'))
    self.assertEqual(self.client.get(reverse('camara')).status_code, 403)

  def test_camara_carga_con_permiso(self):
    self.client.force_login(self.vigilante)
    respuesta = self.client.get(reverse('camara'))
    self.assertContains(respuesta, 'js/camara.js')
    self.assertIn('csrftoken', respuesta.cookies)

  def test_api_usuario_sin_permiso_recibe_403(self):
    self.client.force_login(crear_usuario('sinpermisos'))
    with mock.patch('reconocimiento.views.servicios.reconocer') as reconocer:
      respuesta = self.post_json({'image': 'data:image/jpeg;base64,AAAA'})
    self.assertEqual(respuesta.status_code, 403)
    reconocer.assert_not_called()
    self.assertEqual(RegistroAcceso.objects.count(), 0)

  def test_api_sin_sesion_recibe_403(self):
    self.assertEqual(self.post_json({'image': 'x'}).status_code, 403)

  def test_api_solo_acepta_post(self):
    self.client.force_login(self.vigilante)
    self.assertEqual(self.client.get(self.url).status_code, 405)

  def test_api_exige_csrf(self):
    from django.test import Client
    cliente = Client(enforce_csrf_checks=True)
    cliente.force_login(self.vigilante)
    respuesta = cliente.post(self.url, '{"image": "x"}', content_type='application/json')
    self.assertEqual(respuesta.status_code, 403)

  @mock.patch('reconocimiento.views.servicios.reconocer')
  def test_api_responde_el_contrato_json(self, reconocer):
    reconocer.return_value = [
      self.rostro('Isabella Ardila', self.persona.id),
      self.rostro('Unknown', None, 0.72),
    ]
    self.client.force_login(self.vigilante)
    respuesta = self.post_json({'image': 'data:image/jpeg;base64,AAAA'})
    self.assertEqual(respuesta.status_code, 200)
    self.assertEqual(respuesta.json(), {'faces': [
      {'name': 'Isabella Ardila', 'box': [60, 472, 368, 162]},
      {'name': 'Unknown', 'box': [60, 472, 368, 162]},
    ]})
    reconocer.assert_called_once_with('data:image/jpeg;base64,AAAA')
    self.assertEqual(RegistroAcceso.objects.filter(reconocido=True, persona=self.persona).count(), 1)
    self.assertEqual(RegistroAcceso.objects.filter(reconocido=False).count(), 1)

  @mock.patch('reconocimiento.views.servicios.reconocer')
  def test_api_registra_maximo_una_vez_cada_60_segundos(self, reconocer):
    from datetime import timedelta
    from django.utils import timezone
    reconocer.return_value = [self.rostro('Isabella Ardila', self.persona.id), self.rostro('Unknown', None, 0.8)]
    self.client.force_login(self.vigilante)
    for _ in range(3):
      self.post_json({'image': 'data:image/jpeg;base64,AAAA'})
    self.assertEqual(RegistroAcceso.objects.count(), 2)

    # Pasados 60 segundos se vuelve a registrar
    RegistroAcceso.objects.update(fecha_hora=timezone.now() - timedelta(seconds=61))
    self.post_json({'image': 'data:image/jpeg;base64,AAAA'})
    self.assertEqual(RegistroAcceso.objects.count(), 4)

  def test_api_json_invalido_da_400(self):
    self.client.force_login(self.vigilante)
    respuesta = self.client.post(self.url, 'no es json', content_type='application/json')
    self.assertEqual(respuesta.status_code, 400)
    self.assertEqual(self.post_json({'otra': 'cosa'}).status_code, 400)
    self.assertEqual(self.post_json({'image': 'sin coma'}).status_code, 400)
