from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from .models import Persona, FotoEntrenamiento
from . import servicios


@receiver(post_save, sender=Persona)
@receiver(post_delete, sender=Persona)
@receiver(post_save, sender=FotoEntrenamiento)
@receiver(post_delete, sender=FotoEntrenamiento)
def invalidar_cache_encodings(sender, **kwargs):
  '''
  Cuando cambia una persona (nombre, activo...) o una foto, la caché de
  encodings queda desactualizada y se vuelve a cargar en el siguiente frame.
  '''
  servicios.invalidar_cache()


@receiver(post_delete, sender=FotoEntrenamiento)
def borrar_archivo_foto(sender, instance, **kwargs):
  '''
  Borra el archivo de la carpeta media/ al eliminar la foto.
  '''
  if instance.imagen:
    instance.imagen.delete(save=False)
