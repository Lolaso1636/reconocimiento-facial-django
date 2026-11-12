/*
 * Cámara en vivo: versión en JavaScript puro de los componentes de React
 *   - Camera.tsx      -> captura cada 800 ms, envía al servidor y saluda por voz
 *   - FaceOverlay.tsx -> dibuja los recuadros sobre el video (aquí en un canvas)
 *   - Sidebar.tsx     -> panel lateral con estado, conteo e historial
 */

const INTERVALO_CAPTURA = 800;     // ms, igual que Camera.tsx
const GREETING_COOLDOWN = 10000;   // ms, igual que Camera.tsx
const MAX_HISTORIAL = 5;           // igual que Sidebar.tsx

const COLOR_RECONOCIDO = '#78c028';  // verde UCC
const COLOR_DESCONOCIDO = '#dc2626'; // rojo

const video = document.getElementById('video');
const canvasCaptura = document.getElementById('captura');
const canvasOverlay = document.getElementById('overlay');
const urlApi = document.getElementById('config-camara').dataset.urlApi;

const lastGreet = {};       // última vez que se saludó a cada nombre
let historial = [];         // [{ name, time }]
let intervalo = null;
let enProceso = false;      // evita enviar un frame si el anterior no ha respondido


// ================= CSRF =================
// Django exige el token CSRF en peticiones POST. Se lee de la cookie
// "csrftoken" y se envía en el header X-CSRFToken.
function getCookie(nombre) {
  const valor = document.cookie
    .split(';')
    .map(c => c.trim())
    .find(c => c.startsWith(nombre + '='));
  return valor ? decodeURIComponent(valor.split('=')[1]) : null;
}


// ================= SALUDO POR VOZ (Camera.tsx) =================
function greet(name) {
  const now = Date.now();
  if (now - (lastGreet[name] ?? 0) < GREETING_COOLDOWN) return;
  lastGreet[name] = now;

  const text = name === 'Unknown' ? 'Bienvenido' : `Bienvenido, ${name}`;
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = 'es-ES';
  window.speechSynthesis.speak(utterance);
}


// ================= RECUADROS (FaceOverlay.tsx) =================
function dibujarRecuadros(faces) {
  const ctx = canvasOverlay.getContext('2d');
  ctx.clearRect(0, 0, canvasOverlay.width, canvasOverlay.height);

  faces.forEach(face => {
    const [top, right, bottom, left] = face.box;
    const isUnknown = face.name === 'Unknown';
    const color = isUnknown ? COLOR_DESCONOCIDO : COLOR_RECONOCIDO;
    const etiqueta = isUnknown ? 'Desconocido' : face.name;

    // Recuadro
    ctx.strokeStyle = color;
    ctx.lineWidth = 4;
    ctx.strokeRect(left, top, right - left, bottom - top);

    // Etiqueta con el nombre encima del recuadro
    ctx.font = '600 15px Inter, system-ui, sans-serif';
    const anchoTexto = ctx.measureText(etiqueta).width + 16;
    const yEtiqueta = Math.max(top - 26, 0);
    ctx.fillStyle = color;
    ctx.fillRect(left - 2, yEtiqueta, anchoTexto, 24);
    ctx.fillStyle = isUnknown ? '#ffffff' : '#1e2124';
    ctx.fillText(etiqueta, left + 6, yEtiqueta + 17);
  });
}


// ================= PANEL LATERAL (Sidebar.tsx) =================
function actualizarPanel(faces) {
  document.getElementById('contador-rostros').textContent = faces.length;
  document.getElementById('personas-en-camara').textContent = faces.length;
  document.getElementById('texto-deteccion').textContent =
    faces.length === 0 ? 'Esperando rostro...' : 'Rostro detectado';

  const recognized = faces.find(f => f.name !== 'Unknown');
  const panel = document.getElementById('panel-reconocido');

  if (recognized) {
    panel.classList.remove('hidden');
    document.getElementById('nombre-reconocido').textContent = recognized.name;

    // Igual que Sidebar.tsx: no repetir nombres y guardar solo los últimos 5
    if (!historial.find(p => p.name === recognized.name)) {
      const time = new Date().toLocaleTimeString('es-CO');
      historial = [{ name: recognized.name, time }, ...historial].slice(0, MAX_HISTORIAL);
      pintarHistorial();
    }
  } else {
    panel.classList.add('hidden');
  }
}

function pintarHistorial() {
  const lista = document.getElementById('historial-sesion');
  lista.innerHTML = '';
  historial.forEach(item => {
    const li = document.createElement('li');
    li.className = 'flex justify-between px-3 py-2 rounded-md bg-grafito-50 border border-grafito-100';

    const nombre = document.createElement('span');
    nombre.className = 'font-medium text-grafito-900';
    nombre.textContent = item.name;   // textContent evita inyectar HTML

    const hora = document.createElement('span');
    hora.className = 'text-grafito-500 tabular-nums';
    hora.textContent = item.time;

    li.append(nombre, hora);
    lista.appendChild(li);
  });
}

function ponerEstado(texto, activo) {
  document.getElementById('estado-texto').textContent = texto;
  const estado = document.getElementById('estado-sistema');
  const punto = document.getElementById('estado-punto');
  estado.className = 'flex items-center gap-2 text-sm font-semibold ' + (activo ? 'text-ucc-700' : 'text-red-700');
  punto.className = 'w-2.5 h-2.5 rounded-full ' + (activo ? 'bg-ucc-600 animate-pulse' : 'bg-red-600');
}

function mostrarAviso(texto) {
  const aviso = document.getElementById('aviso');
  aviso.textContent = texto;
  aviso.classList.remove('hidden');
}

function ocultarAviso() {
  document.getElementById('aviso').classList.add('hidden');
}

function detener(texto) {
  clearInterval(intervalo);
  intervalo = null;
  ponerEstado('Detenido', false);
  document.getElementById('indicador-vivo').classList.add('hidden');
  dibujarRecuadros([]);
  mostrarAviso(texto);
}


// ================= CAPTURA Y ENVÍO (Camera.tsx) =================
async function captureFrame() {
  if (enProceso || video.readyState < 2) return;
  enProceso = true;

  try {
    const ctx = canvasCaptura.getContext('2d');
    ctx.drawImage(video, 0, 0, canvasCaptura.width, canvasCaptura.height);
    const base64 = canvasCaptura.toDataURL('image/jpeg');

    const response = await fetch(urlApi, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken'),
      },
      credentials: 'same-origin',
      body: JSON.stringify({ image: base64 }),
    });

    if (response.status === 403) {
      detener('No tienes permiso para registrar accesos o tu sesión expiró. La captura se detuvo; ' +
        'pide a un administrador que te agregue al grupo Vigilante o vuelve a iniciar sesión.');
      return;
    }
    if (!response.ok) {
      throw new Error(`El servidor respondió ${response.status}`);
    }

    const data = await response.json();
    ocultarAviso();
    ponerEstado('Activo', true);
    data.faces.forEach(face => greet(face.name));
    dibujarRecuadros(data.faces);
    actualizarPanel(data.faces);
  } catch (error) {
    // Error temporal (servidor caído, red): se avisa pero se sigue intentando
    ponerEstado('Sin conexión', false);
    mostrarAviso('No se pudo contactar al servidor de reconocimiento. Reintentando...');
    console.error(error);
  } finally {
    enProceso = false;
  }
}


// ================= INICIO =================
function iniciar() {
  // getUserMedia solo existe en contextos seguros: localhost o HTTPS
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    detener('El navegador no permite usar la cámara en esta dirección. Abre el sistema desde ' +
      'http://localhost:8000 o mediante HTTPS.');
    return;
  }

  navigator.mediaDevices.getUserMedia({ video: true })
    .then(stream => {
      video.srcObject = stream;
      ponerEstado('Activo', true);
      intervalo = setInterval(captureFrame, INTERVALO_CAPTURA);
    })
    .catch(error => {
      console.error(error);
      detener('No se pudo acceder a la cámara. Revisa que el navegador tenga permiso para usarla ' +
        'y que ninguna otra aplicación la esté ocupando.');
    });
}

iniciar();
