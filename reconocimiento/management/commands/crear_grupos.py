'''
Crea los grupos base del sistema con sus permisos.

  python manage.py crear_grupos

- Administrador: todos los permisos de la app reconocimiento.
- Vigilante: ver personas, ver historial y registrar accesos (usar la cámara).
'''
from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand


PERMISOS_VIGILANTE = [
  'view_persona',
  'view_registroacceso',
  'add_registroacceso',
]


class Command(BaseCommand):
  help = 'Crea los grupos Administrador y Vigilante con sus permisos'

  def handle(self, *args, **options):
    permisos_app = Permission.objects.filter(content_type__app_label='reconocimiento')

    administrador, _ = Group.objects.get_or_create(name='Administrador')
    administrador.permissions.set(permisos_app)
    self.stdout.write(self.style.SUCCESS(
      f'Grupo "Administrador": {administrador.permissions.count()} permisos'
    ))

    vigilante, _ = Group.objects.get_or_create(name='Vigilante')
    vigilante.permissions.set(permisos_app.filter(codename__in=PERMISOS_VIGILANTE))
    self.stdout.write(self.style.SUCCESS(
      f'Grupo "Vigilante": {vigilante.permissions.count()} permisos'
    ))
