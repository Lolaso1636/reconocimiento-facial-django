from django.shortcuts import render
from django.utils import timezone
from django.contrib.auth.decorators import login_required

from .models import Persona, RegistroAcceso


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
