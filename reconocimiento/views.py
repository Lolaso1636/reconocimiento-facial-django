from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.db.models import Q, Count
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required, user_passes_test
from django.views.decorators.http import require_POST

from .models import Persona, FotoEntrenamiento, RegistroAcceso
from . import servicios
from accounts.views import es_admin


@login_required
def home(request):
  # Las estadísticas solo se muestran si el usuario puede ver personas e historial
  puede_ver = request.user.has_perms([
    'reconocimiento.view_persona',
    'reconocimiento.view_registroacceso',
  ])

  contexto = {'puede_ver': puede_ver}

  if puede_ver:
    hoy = timezone.localdate()
    accesos_hoy = RegistroAcceso.objects.filter(fecha_hora__date=hoy)
    contexto.update({
      'total_personas': Persona.objects.count(),
      'personas_activas': Persona.objects.filter(activo=True).count(),
      'accesos_hoy': accesos_hoy.count(),
      'desconocidos_hoy': accesos_hoy.filter(reconocido=False).count(),
      'ultimos_accesos': RegistroAcceso.objects.select_related('persona')[:5],
      'hoy': hoy,
    })

  return render(request, 'home.html', contexto)


# ================= PERSONAS =================

def procesar_fotos(request, persona, archivos):
  '''
  Crea una FotoEntrenamiento por cada archivo subido y genera su encoding.
  Informa con messages cuántas se procesaron y cuáles fallaron.
  '''
  procesadas = 0
  for archivo in archivos:
    foto = FotoEntrenamiento.objects.create(persona=persona, imagen=archivo)
    exito, mensaje = servicios.generar_encoding(foto)
    if exito:
      procesadas += 1
    else:
      messages.warning(request, f'{archivo.name}: {mensaje}')

  if procesadas:
    messages.success(request, f'{procesadas} foto(s) procesada(s) correctamente.')

  # Si la persona no tiene foto de perfil, se usa la primera foto válida
  if not persona.foto_perfil:
    primera = persona.fotos.filter(procesada=True).first()
    if primera:
      persona.foto_perfil = primera.imagen.name
      persona.save()


def validar_persona(datos, persona=None):
  '''
  Validaciones manuales (como en el registro de accounts).
  '''
  errors = []
  if not datos.get('nombres') or not datos.get('apellidos') or not datos.get('documento'):
    errors.append('Nombres, apellidos y documento son obligatorios.')

  roles_validos = [valor for valor, _ in Persona.ROL_CHOICES]
  if datos.get('rol') not in roles_validos:
    errors.append('Selecciona un rol válido.')

  documentos = Persona.objects.filter(documento=datos.get('documento'))
  if persona:
    documentos = documentos.exclude(id=persona.id)
  if documentos.exists():
    errors.append('Ya existe una persona con ese documento.')
  return errors


@login_required
@permission_required('reconocimiento.view_persona', raise_exception=True)
def personas(request):
  q = request.GET.get('q', '').strip()
  personas = Persona.objects.annotate(
    total_fotos=Count('fotos'),
    fotos_procesadas=Count('fotos', filter=Q(fotos__procesada=True)),
  )
  if q:
    personas = personas.filter(
      Q(nombres__icontains=q) |
      Q(apellidos__icontains=q) |
      Q(documento__icontains=q) |
      Q(programa__icontains=q)
    )
  return render(request, 'personas/lista.html', {'personas': personas, 'q': q})


@login_required
@permission_required('reconocimiento.view_persona', raise_exception=True)
def detalle_persona(request, id):
  persona = get_object_or_404(Persona, id=id)
  accesos = persona.accesos.all()[:50]
  return render(request, 'personas/detalle.html', {
    'persona': persona,
    'fotos': persona.fotos.all(),
    'accesos': accesos,
  })


@login_required
@permission_required('reconocimiento.add_persona', raise_exception=True)
def crear_persona(request):
  datos = ''
  errors = []
  if request.method == "POST":
    datos = request.POST
    errors = validar_persona(datos)

    if not errors:
      persona = Persona.objects.create(
        nombres=datos.get('nombres').strip(),
        apellidos=datos.get('apellidos').strip(),
        documento=datos.get('documento').strip(),
        rol=datos.get('rol'),
        programa=datos.get('programa', '').strip(),
        activo=datos.get('activo') == 'on',
        foto_perfil=request.FILES.get('foto_perfil'),
      )
      procesar_fotos(request, persona, request.FILES.getlist('fotos'))
      messages.success(request, f'Persona {persona.nombre_completo} creada.')
      return redirect('detalle_persona', id=persona.id)

  return render(request, 'personas/crear.html', {
    'errors': errors,
    'datos': datos,
    'rol_choices': Persona.ROL_CHOICES,
  })


@login_required
@permission_required('reconocimiento.change_persona', raise_exception=True)
def editar_persona(request, id):
  persona = get_object_or_404(Persona, id=id)
  errors = []
  if request.method == "POST":
    errors = validar_persona(request.POST, persona)

    if not errors:
      persona.nombres = request.POST.get('nombres').strip()
      persona.apellidos = request.POST.get('apellidos').strip()
      persona.documento = request.POST.get('documento').strip()
      persona.rol = request.POST.get('rol')
      persona.programa = request.POST.get('programa', '').strip()
      persona.activo = request.POST.get('activo') == 'on'
      if request.FILES.get('foto_perfil'):
        persona.foto_perfil = request.FILES.get('foto_perfil')
      persona.save()
      messages.success(request, 'Datos de la persona actualizados.')
      return redirect('detalle_persona', id=persona.id)

  return render(request, 'personas/editar.html', {
    'persona': persona,
    'errors': errors,
    'rol_choices': Persona.ROL_CHOICES,
  })


@require_POST
@login_required
@permission_required('reconocimiento.delete_persona', raise_exception=True)
def eliminar_persona(request, id):
  persona = get_object_or_404(Persona, id=id)
  nombre = persona.nombre_completo
  # Las fotos de entrenamiento se borran en cascada (y sus archivos con la señal)
  if persona.foto_perfil and persona.foto_perfil.name.startswith('personas/'):
    persona.foto_perfil.delete(save=False)
  persona.delete()
  messages.success(request, f'Persona {nombre} eliminada. Sus accesos se conservan en el historial.')
  return redirect('personas')


@require_POST
@login_required
@permission_required('reconocimiento.change_persona', raise_exception=True)
def agregar_foto(request, id):
  persona = get_object_or_404(Persona, id=id)
  archivos = request.FILES.getlist('fotos')
  if archivos:
    procesar_fotos(request, persona, archivos)
  else:
    messages.error(request, 'Selecciona al menos una foto.')
  return redirect('detalle_persona', id=persona.id)


@require_POST
@login_required
@permission_required('reconocimiento.change_persona', raise_exception=True)
def eliminar_foto(request, id):
  foto = get_object_or_404(FotoEntrenamiento, id=id)
  persona = foto.persona
  # Si era la foto de perfil, se reemplaza por otra foto válida
  if persona.foto_perfil.name == foto.imagen.name:
    otra = persona.fotos.filter(procesada=True).exclude(id=foto.id).first()
    persona.foto_perfil = otra.imagen.name if otra else None
    persona.save()
  foto.delete()
  messages.success(request, 'Foto eliminada.')
  return redirect('detalle_persona', id=persona.id)


@require_POST
@user_passes_test(es_admin)
def entrenar(request):
  '''
  Recalcula los encodings de todas las fotos de entrenamiento.
  '''
  procesadas = 0
  fallidas = []
  for foto in FotoEntrenamiento.objects.select_related('persona'):
    exito, mensaje = servicios.generar_encoding(foto)
    if exito:
      procesadas += 1
    else:
      fallidas.append(f'{foto.persona.nombre_completo} (foto {foto.id}): {mensaje}')

  servicios.invalidar_cache()
  messages.success(request, f'Entrenamiento terminado: {procesadas} foto(s) procesada(s), {len(fallidas)} con error.')
  for fallida in fallidas:
    messages.warning(request, fallida)
  return redirect('personas')
