# Sistema de Reconocimiento Facial - UCC (Django)

Aplicación web para la **Universidad Cooperativa de Colombia** que reconoce
rostros en tiempo real desde la cámara del navegador, saluda por voz a la
persona reconocida y guarda un historial de accesos.

**Autores:** Isabella Ardila y David Vargas
**Materia:** Optativa 1 (Django), Ingeniería de Sistemas, Universidad Cooperativa de Colombia, campus Ibagué

## Qué es y relación con la materia

Es el trabajo final de **Optativa 1**. Aplica lo visto en clase sobre un
proyecto de reconocimiento facial:

- Proyecto `core` con dos apps: `reconocimiento` y `accounts`.
- Modelos y ORM, migraciones y panel de administración.
- Vistas basadas en funciones con `request.POST.get`.
- Plantillas con herencia (`layouts/base.html`).
- Autenticación, grupos y permisos con los decoradores `@login_required`,
  `@permission_required`, `@user_passes_test` y `@require_POST`.
- Señales, comandos de gestión propios y pruebas automatizadas.

**Esta versión reemplaza a la anterior**, que estaba hecha con **FastAPI**
(backend) y **React** (frontend) y guardaba los rostros en un archivo
`encodings.pkl`. Django conserva exactamente la misma lógica de reconocimiento.
Ahora los rostros se guardan en la base de datos y se agregaron usuarios,
permisos e historial.

## Pantallas

| Pantalla | Qué muestra |
|---|---|
| **Inicio** | Saludo, tarjetas con personas registradas, accesos de hoy y desconocidos de hoy, y los últimos 5 accesos. Si la cuenta no tiene permisos, muestra un aviso. |
| **Cámara** | Video en vivo con un recuadro verde y el nombre para personas conocidas, y uno rojo con "Desconocido" para el resto. Panel lateral con la última persona detectada y las 5 más recientes. Saludo por voz. |
| **Personas** | Lista con búsqueda, número de fotos y estado. Permite crear, editar y eliminar personas, y subir o quitar fotos de entrenamiento. Cada foto se marca como "Válida" o "Sin rostro válido". |
| **Historial** | Tabla de accesos con filtros por rango de fechas, persona y estado (reconocido o desconocido), paginada de 50 en 50. |
| **Grupos y Permisos** | Solo para staff: crear grupos, asignarles permisos y agregar o quitar usuarios. |
| **Login y Registro** | Páginas de acceso con el logo de la universidad. |

## Fotos de entrenamiento incluidas

La carpeta `fotos_entrenamiento/` tiene las fotos usadas en el proyecto, como
evidencia y para poder probarlo: **8 personas y 57 fotos** (51 válidas; las
demás tienen 0 o más de 1 rostro y el sistema las descarta a propósito).

| Persona | Fotos |
|---|---|
| David Vargas | 7 |
| Ingeniera Nelly | 8 |
| Ingeniero Dennis | 7 |
| Ingeniero Fernando | 4 |
| Ingeniero Oscar | 9 |
| Isabella Ardila | 10 |
| Juan Melo | 5 |
| Miguel Melo | 7 |

Para cargarlas, después de `migrate`:

```powershell
python manage.py importar_fotos fotos_entrenamiento
```

## Cómo probarlo en 5 minutos

Se puede probar con las fotos incluidas (paso opcional abajo) o con fotos propias.

Requisitos: **Python 3.11** y una cámara web.

```powershell
git clone <url-del-repositorio>
cd reconocimiento-facial-django

python -m venv venv
venv\Scripts\activate
pip install --no-deps -r requirements.txt

python manage.py migrate
python manage.py createsuperuser
python manage.py crear_grupos
python manage.py importar_fotos fotos_entrenamiento   # opcional: carga las 8 personas
python manage.py runserver
```

1. Abrir **http://localhost:8000** e iniciar sesión con el superusuario.
2. Ir a **Personas > Nueva persona**, llenar los datos y subir **5 o más fotos
   propias** (de frente, buena luz, una sola cara por foto).
3. Ir a **Cámara** y permitir el acceso a la cámara. Debe aparecer el nombre
   en verde y escucharse el saludo.
4. Ir a **Historial** para ver el acceso registrado.

> `pip install --no-deps` es necesario: `face_recognition` pide el paquete
> `dlib` y pip intentaría compilarlo (falla en Windows sin Visual Studio). El
> `requirements.txt` ya incluye `dlib-bin`, que viene compilado.

## Variables de entorno

La configuración sensible se lee de variables de entorno. Si no se definen, se
usan valores de **desarrollo**, así que para probar en local no hace falta
definir nada.

| Variable | Por defecto | Para producción |
|---|---|---|
| `DJANGO_SECRET_KEY` | Una clave de desarrollo (insegura) | Una clave larga y secreta |
| `DJANGO_DEBUG` | `True` | `False` |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1,[::1]` | El dominio del servidor, separado por comas |

Para generar una clave nueva:

```powershell
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Para definirlas en PowerShell (solo duran mientras la terminal esté abierta):

```powershell
$env:DJANGO_SECRET_KEY = "pegar-aqui-la-clave-generada"
$env:DJANGO_DEBUG = "False"
$env:DJANGO_ALLOWED_HOSTS = "midominio.com"
python manage.py runserver
```

En Linux o macOS se usa `export DJANGO_DEBUG=False`. El archivo `.env` está en
`.gitignore` para que nunca se suban claves al repositorio.

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
.
├── fotos_entrenamiento/   Fotos del proyecto, una subcarpeta por persona
├── core/                  Configuración (settings, urls)
├── accounts/              Login, logout, registro, grupos y permisos
│   └── templates/
└── reconocimiento/
    ├── models.py          Persona, FotoEntrenamiento, RegistroAcceso
    ├── servicios.py       Lógica de reconocimiento facial
    ├── signals.py         Invalida la caché de encodings cuando cambian los datos
    ├── views.py           Vistas basadas en funciones
    ├── admin.py
    ├── management/commands/
    │   ├── importar_fotos.py
    │   └── crear_grupos.py
    ├── static/js/camara.js
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
`fecha_registro`. Solo las personas **activas** se reconocen.

**FotoEntrenamiento**: una foto de una persona (`related_name='fotos'`).
Guarda la `imagen`, el `encoding` (lista de 128 números en un `JSONField`) y si
fue `procesada`. Una foto solo es válida si tiene **exactamente un rostro**.

**RegistroAcceso**: cada detección de la cámara (`related_name='accesos'`).
`persona` (queda vacía si la persona se elimina, `SET_NULL`),
`nombre_detectado`, `distancia`, `reconocido`, `fecha_hora`.

## Cómo funciona el reconocimiento

1. **Detección:** el fotograma se reduce a la mitad y se buscan rostros con el
   modelo **HOG**.
2. **Codificación:** cada rostro pasa por una red neuronal **pre-entrenada** de
   dlib que lo convierte en un vector de 128 números (encoding).
3. **Comparación:** se calcula la distancia con los encodings guardados.
4. **Decisión:** si la menor distancia es **≤ 0.50**, es esa persona; si no,
   "Desconocido". Las coordenadas se multiplican por 2 para volver a 640x480.

No se entrena una red desde cero: se usa el modelo pre-entrenado y solo se
extraen y comparan características. Por eso bastan de 5 a 10 fotos por persona.

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

## Importar muchas fotos a la vez

```powershell
python manage.py importar_fotos "C:\ruta\a\fotos"
```

- Si la carpeta tiene subcarpetas (`fotos\Ana Ruiz\*.jpg`, `fotos\Juan Melo\*.jpg`),
  cada subcarpeta es una persona.
- Si la carpeta tiene imágenes directamente, la carpeta misma es la persona.
- Se asigna un documento provisional `IMP-<nombre>`, que se puede corregir en
  *Personas > Editar*.
- Si se corre dos veces, no duplica las fotos.
- Las fotos sin un rostro claro quedan marcadas como "Sin rostro válido".

Las fotos que se suben desde la aplicación se guardan en `media/`, que está en
`.gitignore`. Las fotos del proyecto están en `fotos_entrenamiento/`.

## La cámara solo funciona en localhost o HTTPS

Los navegadores solo permiten usar la cámara (`getUserMedia`) en un **contexto
seguro**: `http://localhost`, `http://127.0.0.1` o un sitio con **HTTPS**. Si se
abre desde otra máquina con `http://192.168.x.x:8000`, la cámara no arranca y la
página muestra un aviso.

## Pruebas

```powershell
python manage.py test
```

39 pruebas. Cubren la creación de modelos, la caché de encodings, los comandos,
la redirección al login sin sesión, el 403 sin permiso (también en
`api_reconocer`), el CRUD de personas, los filtros del historial, el contrato
JSON de la API (con `servicios.reconocer` simulado), la protección CSRF y la
regla de un registro cada 60 segundos.

## Notas técnicas

- **Caché de encodings:** se carga una vez desde la base de datos y se guarda en
  memoria. Se borra sola (señales `post_save` y `post_delete`) cuando se crea,
  edita o elimina una persona o una foto. Es por proceso: con `runserver` hay
  uno solo.
- **CSRF:** `camara.js` lee la cookie `csrftoken` y la envía en el header
  `X-CSRFToken`.
- **Saludo por voz:** lo hace el navegador (`speechSynthesis`), como máximo una
  vez cada 10 segundos por persona.
- **Un registro cada 60 s:** evita que una persona frente a la cámara genere
  75 registros por minuto (uno cada 800 ms).
