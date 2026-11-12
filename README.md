# Sistema de Reconocimiento Facial - UCC (Django)

Aplicación web para la **Universidad Cooperativa de Colombia** que reconoce
rostros en tiempo real desde la cámara del navegador, saluda por voz a la
persona reconocida y guarda un historial de accesos.

Trabajo final de la materia **Optativa 1 (Django)**, Ingeniería de Sistemas.
Aplica lo visto en clase (proyecto `core`, apps, vistas basadas en funciones,
plantillas con herencia, autenticación, grupos y permisos) sobre un proyecto
de reconocimiento facial que antes estaba hecho con FastAPI y React.

## Versión anterior

En `proyecto_reconocimiento/` siguen las versiones anteriores, que no se borraron:

| Carpeta | Qué era |
|---|---|
| `backend/` | API en FastAPI (`POST /recognize`) que leía los rostros conocidos de `encodings.pkl` |
| `frontend/` | Primera interfaz en HTML y JavaScript |
| `react/reconocimiento-frontend/` | Interfaz en React, TypeScript y Tailwind |

Esta aplicación Django reemplaza a las tres con **la misma lógica de
reconocimiento**. Los rostros conocidos ahora se guardan en la base de datos,
así que ya no se necesita `encodings.pkl`.

## Arquitectura

```
Navegador (camara.html + static/js/camara.js)
   |  cada 800 ms: fotograma JPEG en base64 + token CSRF
   v
POST /api/reconocer/  (views.api_reconocer)
   |  verifica permiso reconocimiento.add_registroacceso
   v
servicios.reconocer()  --usa-->  caché en memoria de encodings
   |  OpenCV + face_recognition (HOG, tolerancia 0.50)    ^
   |                                                      | se invalida con señales
   v                                                      | (signals.py)
RegistroAcceso (máx. 1 por persona cada 60 s)      Persona / FotoEntrenamiento
   |
   v
JSON { faces: [ { name, box: [top, right, bottom, left] } ] }
   |
   v
Navegador: dibuja recuadros, actualiza el panel y saluda por voz
```

```
django_app/
├── core/                  Configuración (settings, urls)
├── accounts/              Login, logout, registro, grupos y permisos (de clase)
│   └── templates/
└── reconocimiento/
    ├── models.py          Persona, FotoEntrenamiento, RegistroAcceso
    ├── servicios.py       Lógica de reconocimiento traída de backend/main.py
    ├── signals.py         Invalida la caché de encodings cuando cambian los datos
    ├── views.py           Vistas basadas en funciones
    ├── admin.py
    ├── management/commands/
    │   ├── importar_fotos.py
    │   └── crear_grupos.py
    ├── static/js/camara.js    Camera.tsx + FaceOverlay.tsx + Sidebar.tsx en JS puro
    ├── static/img/logo_ucc.png
    └── templates/
        ├── layouts/base.html
        ├── home.html, camara.html, historial.html
        └── personas/
```

## Modelos

**Persona**: alguien que el sistema puede reconocer.
`nombres`, `apellidos`, `documento` (único), `rol` (Estudiante, Docente,
Administrativo, Visitante), `programa` (opcional), `activo`, `foto_perfil`,
`fecha_registro`. Tiene la propiedad `nombre_completo`. Solo las personas
**activas** se reconocen.

**FotoEntrenamiento**: una foto de una persona (`related_name='fotos'`).
Guarda la `imagen`, el `encoding` (lista de 128 números en un `JSONField`) y si
fue `procesada`. Una foto solo es válida si tiene **exactamente un rostro**.

**RegistroAcceso**: cada detección de la cámara (`related_name='accesos'`).
`persona` (puede quedar vacía si la persona se elimina, `SET_NULL`),
`nombre_detectado`, `distancia`, `reconocido`, `fecha_hora`. Se ordena del más
reciente al más antiguo.

## Permisos y grupos

| Página | Requisito |
|---|---|
| Inicio | Haber iniciado sesión. Las estadísticas solo se ven con `view_persona` y `view_registroacceso`. |
| Cámara y `/api/reconocer/` | `reconocimiento.add_registroacceso` |
| Personas: ver lista y detalle | `reconocimiento.view_persona` |
| Personas: crear | `reconocimiento.add_persona` |
| Personas: editar, agregar o quitar fotos | `reconocimiento.change_persona` |
| Personas: eliminar | `reconocimiento.delete_persona` |
| Historial | `reconocimiento.view_registroacceso` |
| Reentrenar, Grupos y Permisos | Ser staff (`is_staff`) |

`python manage.py crear_grupos` crea dos grupos:

- **Administrador**: todos los permisos de la app `reconocimiento`.
- **Vigilante**: `view_persona`, `view_registroacceso` y `add_registroacceso`
  (usa la cámara y consulta, pero no modifica personas).

**Registro público:** cualquiera puede crear una cuenta en `/registro/`, pero
**las cuentas nuevas no tienen permisos** hasta que un administrador las agregue
a un grupo (en *Grupos > Editar*). Mientras tanto, el inicio muestra un aviso.

## Instalación (Windows)

Requisitos: **Python 3.11** y una cámara web.

```powershell
cd proyecto_reconocimiento\django_app

# 1. Entorno virtual
python -m venv venv
venv\Scripts\activate

# 2. Dependencias. --no-deps es necesario: face_recognition pide "dlib" y pip
#    intentaría compilarlo. En su lugar se usa dlib-bin (ya compilado).
pip install --no-deps -r requirements.txt

# 3. Base de datos
python manage.py migrate

# 4. Usuario administrador (queda como staff y superusuario)
python manage.py createsuperuser

# 5. Grupos Administrador y Vigilante
python manage.py crear_grupos

# 6. Fotos de entrenamiento: cada subcarpeta es una persona
python manage.py importar_fotos "..\Isabella Ardila"

# 7. Servidor
python manage.py runserver
```

Abrir **http://localhost:8000** e iniciar sesión.

### Sobre `importar_fotos`

- Si la carpeta tiene subcarpetas (`fotos\Ana Ruiz\*.jpg`, `fotos\Juan Melo\*.jpg`),
  cada subcarpeta es una persona.
- Si la carpeta tiene imágenes directamente (como `Isabella Ardila\`), la carpeta
  misma es la persona.
- Se le asigna un documento provisional `IMP-<nombre>`, que se puede corregir en
  *Personas > Editar*.
- Si se corre dos veces, no duplica las fotos.
- Las fotos sin un rostro claro quedan marcadas como "Sin rostro válido" y no se
  usan. Con las fotos de Isabella Ardila se procesan 6 de 10, igual que en el
  `encodings.pkl` original.

### La cámara solo funciona en localhost o HTTPS

Los navegadores solo permiten usar la cámara (`getUserMedia`) en un **contexto
seguro**: `http://localhost`, `http://127.0.0.1` o un sitio con **HTTPS**. Si se
abre desde otra máquina con `http://192.168.x.x:8000`, la cámara no arranca y la
página muestra un aviso.

## Pruebas

```powershell
python manage.py test
```

Cubren la creación de modelos, la caché de encodings, los comandos, la
redirección al login sin sesión, el 403 sin permiso (también en
`api_reconocer`), el CRUD de personas, los filtros del historial y el contrato
JSON de la API (con `servicios.reconocer` simulado). También verifican la regla
de un registro cada 60 segundos.

## Notas técnicas

- **Misma lógica que FastAPI:** el fotograma se reduce a la mitad, se detecta
  con el modelo HOG, se compara con tolerancia 0.50 y las coordenadas del
  recuadro se multiplican por 2 para volver al tamaño original (640x480).
- **Caché de encodings:** se carga una vez desde la base de datos y se guarda en
  memoria. Se borra sola (señales `post_save` y `post_delete`) cuando se crea,
  edita o elimina una persona o una foto. Es por proceso: con `runserver` hay
  uno solo.
- **CSRF:** `camara.js` lee la cookie `csrftoken` y la envía en el header
  `X-CSRFToken`.
- **Saludo por voz:** lo hace el navegador (`speechSynthesis`), igual que en
  React: como máximo una vez cada 10 segundos por persona.
