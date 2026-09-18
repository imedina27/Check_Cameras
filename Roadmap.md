# Roadmap — Check Cameras V2

Basado en la revisión de `Check_Cam_V1`. Enfoque: **refactor incremental** — mismo propósito y arquitectura general, corrigiendo errores, optimizando el código y actualizando módulos clave. Sin rediseño mayor (sin dashboard/DB/alertas por ahora).

Orden: primero corregir lo que está roto o es frágil (Fase 1), luego optimizar el proceso secuencial tal como está (Fase 2), luego modernizar módulos (Fase 3), y al final paralelizar (Fase 4) — a propósito hasta el final, para paralelizar sobre una base ya corregida y optimizada.

## Notas de contexto importantes (no olvidar)

- **El programa es puramente de línea de comandos a propósito.** Corre en dos entornos con visibilidad de red distinta hacia las plantas — no está pensado para convertirse en un servicio/daemon sin repensar esto:
  - **Windows 11 (máquina del usuario):** tiene VPN Zerotier que ve las plantas. Usa `conf/plants/plants.yaml`.
  - **Ubuntu Server "QLYMSPROD01":** ve a los demás servidores directamente por red (sin VPN). Usa `conf/plants/plants_abinbev.yaml`. Aquí hay plantas en la misma red que se pueden agrupar por el campo `plant` del YAML.
- **`plants.yaml` y `plants_abinbev.yaml` NO son duplicados** — son configuraciones paralelas, una por entorno de ejecución. No proponer "unificarlos" sin más; el problema real es que `InfoPlant()` tiene hardcodeado el nombre `plants.yaml`, por lo que cambiar de entorno hoy requiere renombrar archivos a mano (ver Fase 1).

---

## Fase 0 — Preparación del proyecto

- [x] Copiar todos los archivos de `Check_Cam_V1` a la raíz del proyecto (`Check_Cameras`), dejando `Check_Cam_V1` como carpeta de referencia.
- [x] Instalar dependencias en el entorno virtual (`pipenv install`).
- [x] Actualizar `Pipfile` con las dependencias del proyecto y eliminar `requirements.txt` por redundante.
- [x] Hacer commit del proyecto.

---

## Fase 1 — Corrección de errores de programación

- [x] **`main.py` ignora los argumentos reales de CLI.** `sys.argv` se sobreescribe de forma fija a `--plant all` ([main.py:52-54](main.py#L52-L54)), dejando el `argparse` real sin efecto. Quitar el override y dejar que el script use los argumentos reales.
- [x] **Selección de `plants.yaml` vs `plants_abinbev.yaml` está hardcodeada.** Resuelto con una variable `PLANTS_FILE` en `.env` (config.py + `InfoPlant()` en file_processor.py), con default `plants.yaml`. Cada entorno fija su propio valor: `.env` local (Windows) → `plants.yaml`, `AbInBev.env` (plantilla del Ubuntu Server) → `plants_abinbev.yaml`. Al iniciar, se imprime qué archivo se cargó para detectar de inmediato una mala configuración.
- [x] **Gestión de túneles SSH usaba herramientas solo de Unix** (`ss -tulpn`, `os.kill`, `signal.SIGTERM/SIGKILL`, `pkill`). Reemplazado por `psutil` (nueva dependencia) en `check_tunnel_status`, `find_tunnel_pid`, `close_tunnel` y `alternative_close` — una sola implementación que funciona igual en Windows y Linux, sin parsear salida de comandos de shell. También se agregó `get_os()` como helper reutilizable de detección de SO (usado ya en `ping()`). Probado extremo a extremo en Windows: detecta puerto en uso, encuentra el PID real y cierra el proceso correctamente.
- [x] **`locale.setlocale(locale.LC_TIME, 'es_MX.UTF-8')` podía tronar la ejecución completa** si el locale no estaba instalado en la máquina. Reemplazado por un diccionario `MESES_ES` en `file_processor.py`, sin depender del locale del sistema operativo.
- [x] **Sin manejo de claves faltantes en YAML.** `CheckServer()` accedía directo a `dat_server['addresses']['local']`, `dat_server['ia_ports']`, etc. y un YAML de planta incompleto tumbaba toda la corrida. Se agregó validación explícita al inicio de `CheckServer()` (loguea qué campos faltan y salta ese servidor) y un envoltorio `_CheckServerSafe()` en `CheckAll`/`CheckPlant` que aísla cualquier error inesperado por servidor, para que el resto de la corrida continúe.
- [x] **Hallazgo en producción: `open(pid_file, 'w')` tronaba si la carpeta `tmp/` no existía.** Detectado al probar en Ubuntu: todos los servidores `type: tunnels` (casi todos, excepto QLYMSPROD01) fallaban con `FileNotFoundError` al guardar el PID del túnel SSH, abortando toda la revisión de ese servidor antes de llegar a las cámaras (por eso solo tenían `.log`, sin ninguna imagen). `open(..., 'w')` no crea carpetas intermedias. Se agregó `_write_pid_file()` en `system_processor.py` (crea la carpeta con `os.makedirs(..., exist_ok=True)` antes de escribir) y se usó en los 4 lugares donde se guardaba el PID. Probado reproduciendo el escenario exacto (carpeta `tmp` inexistente).
- [x] **Hallazgo en producción: `cam_activate` se trató como obligatorio por error.** Al probar en el servidor Ubuntu real, los 11 servidores de `plants_abinbev.yaml` (que nunca han usado ese campo) se marcaban como "Configuración incompleta" — bug preexistente desde V1 (ahí tronaba el programa completo; nuestra validación de Fase 1 lo hizo más visible pero seguía siendo incorrecto). Se quitó `cam_activate` de `REQUIRED_SERVER_KEYS` y el código ahora usa `dat_server.get('cam_activate', False)`. Se aclaró además la semántica (confirmada con el usuario): `cam_activate: true` filtra cámaras marcadas inactivas en el `cameras.yaml` del servicio IA; `false` revisa todas sin filtrar. Se dejó `cam_activate: false` explícito en los 4 servidores de `plants.yaml` y los 11 de `plants_abinbev.yaml`, para revisar todas las cámaras sin importar su estado individual. Probado: los 11 servidores de AB InBev ya no reportan campos faltantes.
- [x] **Credenciales de cámara expuestas en un `print` de error.** Si `InfoCam_url()` fallaba al parsear una URL, imprimía la URL completa (con usuario/contraseña en texto plano) a consola. Se agregó `mask_credentials()` en `file_processor.py` para enmascarar usuario/contraseña antes de imprimir, usado en ese `except`. El resto del flujo (peticiones HTTP a las cámaras) ya usaba `HTTPDigestAuth`/`HTTPBasicAuth`, que no exponen credenciales en la URL.
- [x] **Excepciones genéricas que ocultaban la causa real.** Se revisaron todos los `except Exception`/`except:` del proyecto: la mayoría en `system_processor.py` ya imprimían el error real y estaban bien como red de seguridad. Se corrigieron los dos casos silenciosos/engañosos: `InfoPlant()` (ya no descarta el error, lo imprime) y `read_yaml()` (el catch-all ya no reporta un error inesperado como "HTTP error [413]" — se agregó el código 415 "Unexpected error" para distinguirlo). También se corrigió `ping()`, que descartaba el error sin dejar rastro.
- [x] **Variables de `.env` que no coinciden con `config.py`.** `config.py` ahora lee `MAX_AI_RETRIES`/`AI_IMAGE_TIMEOUT` (antes buscaba `MAX_IMAGE_RETRIES`/`IMAGE_TIMEOUT`, que no existían en el `.env`). También se corrigió `PX_PID_FILE`/`IA_PID_FILE`, que ambas leían por error la misma clave inexistente `PID_FILE`.

## Fase 2 — Optimización de código

> La paralelización (el mayor cuello de botella) se pospuso a propósito hasta el final — ver **Fase 4**. Primero se mejora el proceso tal como está hoy (secuencial).

- [x] **Reutilizar sesiones HTTP.** Cada `Camera` ahora crea un `requests.Session()` compartido entre `Cam_Up`, `Cam_AI_Image`, `Cam_Image` y `Cam_Config` (y sus funciones de marca en `conf/cameras/*.py`, que ahora reciben `session` como parámetro en vez de usar `requests` directo). Probado extremo a extremo con un servidor HTTP local: las 6 peticiones de `DahuaCamConf` reutilizaron la misma conexión TCP en vez de abrir una nueva por cada una.
- [x] **Revisar acumulación de timeouts.** Decisión: no forzar un límite que corte reintentos — el objetivo de la herramienta es intentar todo lo posible por conseguir las 3 evidencias de cada cámara, no ser rápida. En vez de un techo que salte cámaras, se dará **visibilidad** del tiempo con un cronómetro por cámara — ver **Fase 4** (se hace justo antes de paralelizar, para poder comparar el tiempo total antes/después).
- [x] **Evitar trabajo repetido en `dirs_path()`/`log_processor()`.** Cada línea de log repetía `os.makedirs()` y `os.path.isfile()` (llamadas al sistema de archivos) para la misma carpeta/archivo, decenas de veces por servidor. Se agregó una caché en memoria (`_dirs_ensured` para directorios; el caché de loggers de la migración a `logging` en Fase 3 cubre el archivo) para que cada carpeta/archivo se verifique una sola vez por corrida. Probado con 50 llamadas seguidas al mismo servidor: `os.makedirs`/`os.path.isfile` se ejecutaron 1 sola vez cada uno (antes: 50), sin duplicar encabezados ni cambiar el contenido del log.

## Fase 3 — Actualización de módulos

- [x] **Reemplazar el despacho de marca por if/elif** en `cameras.py` (`Cam_Image`, `Cam_Config`) por un registro (`CAMERA_HANDLERS`, dict marca → `(func_imagen, func_config)`). Se uniformaron las firmas de las 8 funciones de marca (todas aceptan `channel=1`, aunque no todas lo usen aún) para que el registro no necesite casos especiales. Se dejó un comentario junto a `CAMERA_HANDLERS` recordando que `resolve_brand()` (`file_processor.py`) también debe actualizarse al agregar una marca — es un mapeo aparte (URL → marca) que no vive en el registro. Probado con las 4 marcas contra un servidor local + caso de marca desconocida (620/720).
- [x] **Unificar gestión de dependencias.** Resuelto en Fase 0: se eliminó `requirements.txt` y `Pipfile` quedó como única fuente de verdad.
- [x] **Logging estructurado (núcleo).** `log_processor()` en `file_processor.py` ahora usa el módulo `logging`: un logger por archivo (`FileHandler` + `StreamHandler` coloreado por nivel real, no por texto). Se quitó el prefijo redundante `[SUCCESS]/[WARNING]/[ERROR]` de `config.STATUS_MESSAGES` en pantalla/archivo (ya lo indica el nivel). Se eliminó el parámetro `add_timestamp` (ya no aplica: cada línea lleva timestamp automático) y se actualizaron las ~28 llamadas en `check.py`. Ajuste tras verlo corriendo en producción: las líneas estructurales (separadores, "Camera: X IP: Y") se muestran como `INFO` en texto pero **sin color** (nivel interno `STRUCTURE_LEVEL`), dejando el verde reservado a éxitos reales y el rojo a errores reales — así se distingue de un vistazo el cambio de servidor/cámara. Probado extremo a extremo con un servidor simulado (éxito y error), 20 llamadas repetidas al mismo servidor (sin duplicar handlers ni líneas), y verificación directa del formateador de color (estructural sin color, éxito verde, error rojo).
- [x] **Logging estructurado (barrido de `print()` sueltos).** Decisión: se pospuso a **Fase 4**, antes de la sección de paralelización (ver ahí el detalle y el orden).
- [x] **Resumen final de ejecución.** `CheckServer()` ahora regresa un resultado estructurado (servidor: problema o no + lista de cámaras con sus fallas), que `CheckAll`/`CheckPlant` acumulan y pasan a `write_summary()` (`file_processor.py`). Genera `resumen_dd-mm-aaaa.log` en la carpeta del día, con totales (servidores OK/con problemas, cámaras completas/con falla) y el detalle por planta de qué cámara falló y en qué paso. Solo aplica a `CheckAll` (siempre) y a `CheckPlant` cuando encuentra más de un servidor. Probado con 2 servidores (uno con configuración incompleta, otro con cámaras fallidas), verificado que no se genera con un solo servidor, y validado contra un resumen real de producción (88 cámaras). Ajuste tras verlo en producción: el detalle por planta ahora alinea en columnas (nombre de cámara e IP) según el más largo de cada planta, para que sea fácil de escanear visualmente.
- [x] **Pruebas automatizadas básicas.** Se agregó `pytest` (dev-dependency en `Pipfile`) y una carpeta `tests/` con 32 pruebas para funciones puras (sin red): `resolve_brand`, `InfoCam_url`, `mask_credentials` (incluyendo el caso de contraseña con `@`), `dic_to_json`/`txt_to_json` de las 4 marcas (incluyendo el caso límite de Axis/Vivotek perdiendo una línea con `=` en el valor, que Dahua sí conserva), `status_text`/`is_success_code`, y la validación de campos faltantes de `CheckServer()`. Correr con `pipenv run pytest`. Las 32 pruebas pasan.
- [x] **Hallazgo (Fase 1 revisited): `HikvCamConf` no atrapaba errores de XML malformado.** Solo capturaba `requests.exceptions.RequestException`; si la cámara respondía algo que `xmltodict` no podía parsear, la excepción (`xml.parsers.expat.ExpatError`) tumbaba toda la corrida. Se agregó el catch específico en `hikvision.py`, que ahora imprime el error real y devuelve 790 sin tronar. Probado con una respuesta XML malformada.

---

## Fase 4 — Paralelización

Se hace al final, una vez que el proceso secuencial ya esté optimizado y estable (Fases 1-3). Orden interno de esta fase: primero el barrido de logging, luego el cronómetro, al final la paralelización — cada uno se verifica en secuencial antes de mezclarlo con concurrencia.

### Barrido de `print()` sueltos hacia el log correcto (antes de paralelizar)

Se hace **antes** de paralelizar (no después): así cualquier cambio de firma/lógica se verifica en un entorno secuencial y determinista, sin mezclarlo con bugs de concurrencia al mismo tiempo.

- [x] **Enviar los `print()` huérfanos al log de la planta/servidor correcto**, no solo a consola. Implementado para las funciones que aplicaban:
  - **Túneles (`system_processor.py`):** `create_tunnel()`/`close_tunnel()` ahora reciben `plant` (y `close_tunnel()` también `serv_name`, que antes no recibía en absoluto), e internamente usan `log_processor()` en vez de `print()` — se importó `log_processor` desde `file_processor.py` (sin ciclo de imports, verificado). Las funciones auxiliares más internas (`find_tunnel_pid`, `check_tunnel_status`, `alternative_close`) se dejaron con `print()` por ahora, fuera de alcance de este punto.
  - **`ping()`, `read_yaml()`, `InfoCam_url()`:** se les agregó `plant`/`server` como parámetros **opcionales** (default `None`) — `log_processor()` ya maneja `None` sin tronar (cae a una carpeta/archivo `ERROR` genérico), así que siguen funcionando igual si se llaman sin contexto (ej. en las pruebas de pytest).
  - Se actualizaron todos los call sites en `check.py` para pasar `plant`/`serv_name`.
  - Probado extremo a extremo: falla de túnel simulada (sin red real) queda registrada en el log de la planta/servidor correcto; error de `read_yaml()` igual. Las 32 pruebas de pytest siguen pasando sin cambios (compatibilidad hacia atrás confirmada).
- [x] **Hallazgo en producción: `Cam_Image()`/`Cam_Config()` de las 4 marcas descartaban el detalle real del error.** Al probar en Ubuntu, varias cámaras mostraban "Configuración: Unknow error [790]" sin ninguna pista de la causa — `axis.py`/`dahua.py`/`vivotek.py` ni siquiera imprimían la excepción (`except requests.exceptions.RequestException as e: return 790`, la `e` nunca se usaba); solo Hikvision tenía un `print()` para el caso de XML inválido, y ni ese quedaba en el log. Se agregó `plant`/`server` opcionales a las 8 funciones de marca (`CamImage`/`CamConf` × 4), y ahora todas registran el detalle real (vía `log_processor()`) antes de regresar el código de error — incluyendo, para Hikvision/Dahua, cuál de las peticiones secuenciales de configuración falló. Probado extremo a extremo simulando un 401: el log ahora muestra "401 Client Error: Unauthorized..." en vez de solo "790".

### Cronómetro y visibilidad de tiempos por cámara (justo antes de paralelizar)

Se implementa aquí, inmediatamente antes de paralelizar, para poder comparar con datos reales el tiempo total antes/después del paralelismo.

- [x] **Cronómetro por cámara + log coloreado según umbral.** Un cronómetro (`time.perf_counter()`) arranca antes de `Cam_Up()` y se detiene justo después de `Cam_Config()` (un solo tiempo total, no desglosado por paso), justo antes del separador `====` de esa cámara. Se agregó `log_camera_time()` en `file_processor.py`: verde (`INFO`) si el tiempo quedó dentro de `config.CAM_TIME_THRESHOLD`, **amarillo** (`WARNING`) si lo excedió — el rojo queda reservado para errores reales, no para "solo lento". No se salta ni se cancela nada, es solo visibilidad. Umbral calculado con 3 logs reales de producción (QLYMSPROD01/02 locales en Zacatecas, QLYMSPROD05 por túnel en Tocancipa): se encontró que cámaras sanas pueden tardar 12-14s por diseño (Hikvision/Dahua hacen varias peticiones para armar su configuración, vs. 1 sola en Axis/Vivotek) independientemente de si es local o por túnel — se definió `CAM_TIME_THRESHOLD=15` (segundos) en `.env`/`AbInBev.env` como punto de partida, ajustable. Probado extremo a extremo: color correcto según umbral, e integrado en el ciclo real de `CheckServer()`.

### Paralelización

- [x] **Definir y crear los procesos de paralelización.** El procesamiento de cada cámara (`Cam_Up` + `Cam_AI_Image` + `Cam_Image` + `Cam_Config` + cronómetro) se extrajo a `_process_camera()`/`_process_camera_safe()` (esta última aísla errores, mismo patrón que `_CheckServerSafe()`) en `check.py`. El `for` secuencial de cámaras se reemplazó por `concurrent.futures.ThreadPoolExecutor(max_workers=config.MAX_CAMERA_WORKERS)` (I/O-bound, no requiere `asyncio`). Nueva variable `MAX_CAMERA_WORKERS=5` en `.env`/`AbInBev.env`/`config.py`, ajustable después con datos reales. Servidores entre sí se mantienen secuenciales — ver nota abajo.
  - **Cada línea de log ahora lleva el alias de la cámara al frente** (vía nuevo parámetro `prefix` en `log_processor()`), porque varias cámaras corren a la vez y sus líneas se intercalan en el log del servidor — sin el alias sería imposible saber de qué cámara es cada línea.
  - **Bug de concurrencia corregido antes de activar el paralelismo:** el caché de loggers de Fase 3 (`_get_server_logger()`) no era seguro para hilos — dos cámaras del mismo servidor logueando por primera vez casi al mismo tiempo podían duplicar los manejadores (líneas repetidas). Se agregó un `threading.Lock()` con patrón double-checked-locking. También se protegió con el mismo candado la escritura directa de líneas en blanco (bypaseaba el lock interno del `Handler`).
  - Probado extremo a extremo con 10 cámaras simuladas y 5 workers: **10.36s en paralelo vs. ~50s estimados en secuencial** (~5x, coincide con el número de workers), **0 líneas duplicadas** en el log, y alias correctamente distinguible en cada línea intercalada.
- [ ] **No paralelizar servidores entre sí (por ahora).** Cuando `type: tunnels`, el túnel usa un puerto local fijo y compartido (`IA_LOC_PORT`/`PX_LOC_PORT`); dos servidores con túnel corriendo al mismo tiempo se "pisarían" el puerto. Paralelizar servidores requeriría antes resolver la asignación de puertos locales únicos por túnel concurrente — se deja fuera de alcance por ahora.
- [x] **Logging seguro para concurrencia.** Resuelto de forma anticipada en Fase 3 para la escritura de cada línea (los `Handler` ya traen su candado interno), y se completó ahora con el candado en `_get_server_logger()` para la creación del logger (ver arriba) — ese caso específico no estaba cubierto por el candado interno del `Handler`.

---

## Mejoras / Actualizaciones del Programa

Puntos identificados sobre la marcha, sin una fase fija todavía. Se revisan paso a paso cuando lleguemos a cada uno.

- [ ] **Revisión y homologación de archivos de configuración.** `dic_to_json()` (Axis/Dahua) y `txt_to_json()` (Vivotek) parsean el texto plano de configuración de cada marca con reglas distintas entre sí (separador `.` vs `_`, comillas en el valor, prefijo a omitir) porque así responde cada cámara — no es necesariamente algo a "unificar" a la fuerza, pero vale la pena revisar juntos: la inconsistencia de robustez encontrada (Axis/Vivotek pierden silenciosamente una línea si el valor trae un `=`; Dahua no) y si conviene una función común parametrizada en vez de 3 casi-iguales.
- [ ] **Rediseñar cómo `Cam_Config()` solicita la configuración de la cámara.** El usuario planea mejorar/optimizar este proceso (por ejemplo, Hikvision/Dahua hoy hacen 4-6 peticiones HTTP secuenciales solo para armar la configuración). **Contexto/hallazgo relevante para cuando se aborde:** en producción, varias cámaras Hikvision fallaban con `RemoteDisconnected('Remote end closed connection without response')` justo en la primera de esas peticiones — hipótesis: la cámara corta la conexión TCP persistente (reutilizada desde Fase 2 vía `requests.Session()`) después de varias peticiones seguidas (`Cam_Up` + `Cam_Image` + las 4-6 de `Cam_Config` = 6-8 peticiones en una sola conexión hacia la cámara). No se parcheó con un reintento porque este punto va a rediseñar la solicitud de fondo; considerarlo al definir el nuevo enfoque (nota: `Cam_AI_Image()` no cuenta para este presupuesto — pega al servidor/servicio IA, no a la cámara, va en un pool de conexión aparte).

---

## Último paso — Documentación

Se hace al final de todo, una vez que el código ya no se va a seguir moviendo — así se documenta una sola vez el estado final, en vez de tener que reescribirlo cada vez que algo cambie mientras avanzamos.

- [ ] **`README.md` del proyecto.** Documentar datos generales del programa. Por lo pronto: uso del programa (comandos de `main.py`) y pasos para agregar una marca de cámara nueva.

---

## Fuera de alcance para V2 (posible V3)

- Dashboard web / interfaz gráfica.
- Base de datos histórica de resultados.
- Alertas automáticas (correo/Slack/Teams) ante fallas.
