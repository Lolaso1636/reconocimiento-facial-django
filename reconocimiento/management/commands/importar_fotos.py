'''
Importa fotos de entrenamiento desde carpetas.

  python manage.py importar_fotos "<carpeta>"

- Si <carpeta> tiene subcarpetas, cada subcarpeta es una persona y su nombre
  es el nombre de la persona (ej: "fotos/Isabella Ardila/*.jpeg").
- Si <carpeta> tiene imágenes directamente, la carpeta misma es la persona
  (ej: "../Isabella Ardila").

La primera palabra del nombre se toma como nombres y el resto como apellidos.
Como el documento es obligatorio y único, se asigna uno provisional
"IMP-<nombre>" que se puede corregir luego desde Personas > Editar.
'''
from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand, CommandError

from reconocimiento.models import Persona, FotoEntrenamiento
from reconocimiento import servicios


EXTENSIONES = {'.jpg', '.jpeg', '.png'}


def es_imagen(ruta):
  return ruta.is_file() and ruta.suffix.lower() in EXTENSIONES


class Command(BaseCommand):
  help = 'Crea Personas y FotoEntrenamiento a partir de carpetas de fotos y genera sus encodings'

  def add_arguments(self, parser):
    parser.add_argument('carpeta', help='Carpeta con subcarpetas por persona, o carpeta de una sola persona')

  def handle(self, *args, **options):
    carpeta = Path(options['carpeta']).resolve()
    if not carpeta.is_dir():
      raise CommandError(f'La carpeta "{carpeta}" no existe.')

    if any(es_imagen(r) for r in carpeta.iterdir()):
      carpetas_personas = [carpeta]
    else:
      carpetas_personas = sorted(r for r in carpeta.iterdir() if r.is_dir())

    if not carpetas_personas:
      raise CommandError('No se encontraron imágenes ni subcarpetas.')

    total_ok = 0
    total_fallidas = 0

    for carpeta_persona in carpetas_personas:
      nombre = carpeta_persona.name.strip()
      partes = nombre.split(' ', 1)
      nombres = partes[0]
      apellidos = partes[1] if len(partes) > 1 else ''

      persona, creada = Persona.objects.get_or_create(
        documento=f'IMP-{nombre}'[:20],
        defaults={'nombres': nombres, 'apellidos': apellidos, 'rol': 'ESTUDIANTE'},
      )
      estado = 'creada' if creada else 'ya existía'
      self.stdout.write(f'\nPersona {persona.nombre_completo} ({estado})')

      # No volver a importar fotos que ya se importaron (mismo nombre de archivo)
      ya_importadas = {Path(f.imagen.name).name for f in persona.fotos.all()}
      foto_storage = FotoEntrenamiento._meta.get_field('imagen').storage

      for ruta in sorted(carpeta_persona.iterdir()):
        if not es_imagen(ruta):
          continue
        # Django guarda el archivo con un nombre "seguro" (espacios -> _)
        if foto_storage.get_valid_name(ruta.name) in ya_importadas:
          self.stdout.write(f'  - {ruta.name}: ya importada, se omite')
          continue

        foto = FotoEntrenamiento(persona=persona)
        with open(ruta, 'rb') as archivo:
          foto.imagen.save(ruta.name, File(archivo), save=True)

        exito, mensaje = servicios.generar_encoding(foto)
        if exito:
          total_ok += 1
          self.stdout.write(self.style.SUCCESS(f'  - {ruta.name}: {mensaje}'))
        else:
          total_fallidas += 1
          self.stdout.write(self.style.WARNING(f'  - {ruta.name}: {mensaje}'))

      if not persona.foto_perfil:
        primera = persona.fotos.filter(procesada=True).first()
        if primera:
          persona.foto_perfil = primera.imagen.name
          persona.save()

    self.stdout.write(self.style.SUCCESS(
      f'\nListo: {total_ok} fotos procesadas, {total_fallidas} sin rostro válido.'
    ))
