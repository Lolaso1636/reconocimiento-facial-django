'''
Servicio de reconocimiento facial.

Es la misma lógica de backend/main.py (FastAPI), pero los encodings conocidos
se leen de la base de datos (FotoEntrenamiento.encoding) en lugar de
encodings.pkl.
'''
import base64
import threading

import cv2
import numpy as np
import face_recognition

from .models import FotoEntrenamiento


# ================= CONFIG (igual que backend/main.py) =================
DIST_THRESHOLD = 0.50
DETECTOR_MODEL = "hog"
SCALE = 0.5


# ================= CACHÉ DE ENCODINGS CONOCIDOS =================
# Leer la base de datos en cada frame (cada 800 ms) sería lento, así que los
# encodings se guardan en memoria. Las señales de signals.py llaman a
# invalidar_cache() cuando cambia una Persona o una FotoEntrenamiento.
_cache = None
_cache_lock = threading.Lock()


def invalidar_cache():
  global _cache
  with _cache_lock:
    _cache = None


def obtener_encodings_conocidos():
  '''
  Devuelve (encodings, nombres, persona_ids) solo de personas activas.
  Cada foto procesada aporta un encoding (una persona puede tener varios),
  igual que en encodings.pkl.
  '''
  global _cache
  with _cache_lock:
    if _cache is None:
      fotos = FotoEntrenamiento.objects.filter(
        procesada=True,
        encoding__isnull=False,
        persona__activo=True,
      ).select_related('persona')

      encodings = []
      nombres = []
      persona_ids = []
      for foto in fotos:
        encodings.append(np.array(foto.encoding))
        nombres.append(foto.persona.nombre_completo)
        persona_ids.append(foto.persona.id)

      _cache = (encodings, nombres, persona_ids)
      print(f"[INFO] Cache cargada con {len(encodings)} encodings")
    return _cache


# ================= ENTRENAMIENTO =================
def generar_encoding(foto):
  '''
  Calcula y guarda el encoding de una FotoEntrenamiento.
  La foto debe tener exactamente un rostro.
  Devuelve (exito, mensaje).
  '''
  try:
    imagen = face_recognition.load_image_file(foto.imagen.path)
  except Exception as e:
    foto.encoding = None
    foto.procesada = False
    foto.save()
    return False, f"No se pudo abrir la imagen: {e}"

  ubicaciones = face_recognition.face_locations(imagen, model=DETECTOR_MODEL)

  if len(ubicaciones) != 1:
    foto.encoding = None
    foto.procesada = False
    foto.save()
    if len(ubicaciones) == 0:
      return False, "No se detectó ningún rostro en la foto."
    return False, f"Se detectaron {len(ubicaciones)} rostros; la foto debe tener solo uno."

  encoding = face_recognition.face_encodings(imagen, ubicaciones)[0]
  foto.encoding = [float(valor) for valor in encoding]
  foto.procesada = True
  foto.save()
  return True, "Encoding generado correctamente."


# ================= RECONOCIMIENTO =================
def reconocer(imagen_base64):
  '''
  Recibe un data URL ("data:image/jpeg;base64,...") y devuelve una lista de
  { name, box: [top, right, bottom, left], distancia, persona_id }.
  Lanza ValueError si el texto no es una imagen base64 válida.
  '''
  try:
    image_data = imagen_base64.split(",")[1]
    image_bytes = base64.b64decode(image_data)
  except (IndexError, ValueError, AttributeError):
    raise ValueError("La imagen no tiene el formato data URL base64 esperado.")

  np_arr = np.frombuffer(image_bytes, np.uint8)
  frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

  if frame is None:
    return []

  # Reducir tamaño para detectar más rápido (igual que main.py)
  small_frame = cv2.resize(frame, (0, 0), fx=SCALE, fy=SCALE)
  rgb_small = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
  rgb_small = np.ascontiguousarray(rgb_small)

  face_locations = face_recognition.face_locations(rgb_small, model=DETECTOR_MODEL)

  if len(face_locations) == 0:
    return []

  face_encodings = face_recognition.face_encodings(rgb_small, face_locations)

  known_face_encodings, known_face_names, known_persona_ids = obtener_encodings_conocidos()

  results = []

  for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):

    distances = face_recognition.face_distance(known_face_encodings, face_encoding)

    # Igual que main.py: sin encodings conocidos el rostro se omite
    if len(distances) == 0:
      continue

    best_idx = np.argmin(distances)
    best_distance = float(distances[best_idx])

    if best_distance <= DIST_THRESHOLD:
      name = known_face_names[best_idx]
      persona_id = known_persona_ids[best_idx]
    else:
      name = "Unknown"
      persona_id = None

    # Escalar coordenadas al tamaño original del frame (igual que main.py)
    results.append({
      "name": name,
      "box": [
        int(top / SCALE),
        int(right / SCALE),
        int(bottom / SCALE),
        int(left / SCALE)
      ],
      "distancia": best_distance,
      "persona_id": persona_id,
    })

  return results
