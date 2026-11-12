from django.contrib.auth.models import User, Group
from django.test import TestCase
from django.urls import reverse


class RegistroTest(TestCase):

  def test_registro_crea_usuario_sin_permisos(self):
    respuesta = self.client.post(reverse('registro'), {
      'username': 'nuevo', 'email': 'nuevo@ucc.edu.co',
      'first_name': 'Nuevo', 'last_name': 'Usuario',
      'password1': 'Clave-Segura-123', 'password2': 'Clave-Segura-123',
    })
    self.assertRedirects(respuesta, reverse('home'))
    usuario = User.objects.get(username='nuevo')
    self.assertEqual(usuario.groups.count(), 0)
    self.assertFalse(usuario.has_perm('reconocimiento.view_persona'))

  def test_registro_valida_contrasenas(self):
    respuesta = self.client.post(reverse('registro'), {
      'username': 'nuevo', 'email': 'nuevo@ucc.edu.co',
      'password1': 'a', 'password2': 'b',
    })
    self.assertContains(respuesta, 'Las contraseñas no coinciden.')
    self.assertFalse(User.objects.filter(username='nuevo').exists())


class GruposTest(TestCase):

  def setUp(self):
    self.admin = User.objects.create_user('admin', password='x', is_staff=True)
    self.normal = User.objects.create_user('normal', password='x')

  def test_grupos_solo_staff(self):
    self.client.force_login(self.normal)
    respuesta = self.client.get(reverse('grupos'))
    self.assertEqual(respuesta.status_code, 302)
    self.assertIn(reverse('login'), respuesta.url)

  def test_admin_crea_grupo_y_agrega_usuario(self):
    self.client.force_login(self.admin)
    self.client.post(reverse('grupos'), {'nombre_grupo': 'Vigilante'})
    grupo = Group.objects.get(name='Vigilante')
    self.client.post(reverse('agregar_usuario_grupo', args=[grupo.id]), {'id_user': self.normal.id})
    self.assertIn(self.normal, grupo.user_set.all())
    self.client.post(reverse('eliminar_usuario_grupo', args=[grupo.id]), {'id_user': self.normal.id})
    self.assertNotIn(self.normal, grupo.user_set.all())

  def test_paginas_de_admin_cargan(self):
    self.client.force_login(self.admin)
    grupo = Group.objects.create(name='Vigilante')
    for url in [reverse('grupos'), reverse('editar_grupo', args=[grupo.id]), reverse('permisos')]:
      self.assertEqual(self.client.get(url).status_code, 200, url)
