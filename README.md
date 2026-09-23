# Check Cameras

Herramienta de línea de comandos para verificar el estado de cámaras IP (Axis, Hikvision, Vivotek, Dahua) en las plantas de la operación. Por cada cámara activa, confirma que el puerto 80 responda y descarga tres evidencias: la imagen procesada por el servicio de IA del servidor, la imagen directa de la cámara, y su configuración — dejando todo organizado en carpetas por fecha/planta/servidor, con un log detallado y un resumen final de la corrida.

## Requisitos previos

- Python 3.14 (ver `Pipfile`).
- [`pipenv`](https://pipenv.pypa.io/) para manejar el entorno virtual y las dependencias.
- Cliente `ssh` configurado con autenticación por llave (sin contraseña interactiva) si vas a revisar servidores con `type: tunnels` — el programa abre el túnel invocando `ssh` directamente, no puede detenerse a pedir una contraseña.

## Instalación

```bash
git clone <url-del-repositorio>
cd Check_Cameras
pipenv install
```

Después, crea tu configuración local a partir de las plantillas (ver siguiente sección):

```bash
cp .env.example .env
cp conf/plants/plants.yaml.example "conf/plants/Nombre_Cliente.yaml"
```

Y ajusta ambos archivos con los datos reales de tu red — **ninguno se sube al repositorio** (están en `.gitignore` porque traen direcciones IP internas y rutas específicas de cada máquina).

## Los dos entornos de ejecución

El programa es puramente de línea de comandos a propósito, porque corre en dos entornos con visibilidad de red distinta hacia las plantas:

- **Windows (máquina local):** tiene una VPN Zerotier que ve las plantas remotamente.
- **Ubuntu Server:** ve a los demás servidores directamente por red, sin VPN. Aquí normalmente hace falta túnel SSH (`type: tunnels`) para alcanzar servidores fuera de su red directa.

Cada entorno tiene su propio `.env` y sus propios archivos de cliente en `conf/plants/` — no son intercambiables, cada uno refleja las IPs/puertos que esa máquina específica puede alcanzar. Un archivo de cliente que no aplique a esa máquina (ej. un cliente de Ubuntu, guardado de referencia en la máquina Windows) se guarda en una subcarpeta cualquiera dentro de `conf/plants/` (ej. `conf/plants/other_clients/`) — el descubrimiento de clientes **no** es recursivo a propósito, así que cualquier subcarpeta queda automáticamente fuera de la revisión.

## Configuración

### `.env`

Ver `.env.example` para la plantilla completa con todos los valores y sus comentarios. Los grupos principales son:

| Variable | Para qué sirve |
| --- | --- |
| `LOCAL_HOST` | Nombre de esta máquina; el programa lo usa para detectar si el servidor a revisar es "este mismo servidor". |
| `RESULT_PATH` | Prefijo común de resultados. Cada cliente descubierto en `conf/plants/*.yaml` cuelga de aquí en su propia subcarpeta (`RESULT_PATH/<client_id>/...`), creada sola si no existe. |
| `MAX_PING_ATTEMPTS`, `PING_TIMEOUT`, `RETRY_DELAY` | Reintentos/tiempos del ping a los servidores. |
| `MAX_CAMERA_RETRIES`, `CAMERA_PORT_TIMEOUT`, `PORT80_DELAY` | Reintentos/tiempos al revisar el puerto 80 de cada cámara. |
| `MAX_AI_RETRIES`, `AI_IMAGE_TIMEOUT` | Reintentos/tiempo al pedir la imagen procesada por IA. |
| `CONF_TIMEOUT` | Tiempo de espera al descargar la configuración de una cámara. |
| `MAX_CONFIG_RETRIES`, `CONFIG_RETRY_DELAY` | Reintentos/tiempo de espera al descargar la configuración de una cámara si falla (mitiga fallas transitorias de conexión bajo concurrencia). |
| `YAML_TIMEOUT` | Tiempo de espera al leer el YAML de cámaras del servicio IA. |
| `IA_LOC_PORT`, `PX_LOC_PORT`, `IA_PID_FILE`, `PX_PID_FILE` | Solo aplican a servidores `type: tunnels` — puertos locales y archivos de PID de los túneles SSH. |
| `MAX_RETRIES` | Reintentos al cerrar un túnel SSH. |
| `CAM_TIME_THRESHOLD` | Segundos "normales" para el proceso completo de una cámara — si se excede, se loguea en amarillo (solo visibilidad, no cancela nada). |
| `MAX_CAMERA_WORKERS` | Cuántas cámaras de un mismo servidor se revisan en paralelo. |
| `LOG_SORT_STRATEGY` | Orden de servidores/plantas en el resumen (ver `sort_strategies.py`). `alphabetical` (por nombre) o `numeric_suffix` (por el número al final del nombre del servidor, ej. `QLYMSPROD01`, `QLYMSPROD02`...). |

### Archivos de cliente (`conf/plants/*.yaml`)

Un archivo YAML **por cliente** en `conf/plants/` — no un solo archivo mezclando todos los clientes. Cada uno es una lista de servidores bajo la clave `servers` (ver `conf/plants/plants.yaml.example` para la plantilla); mismo esquema para todos los clientes:

| Campo | Para qué sirve |
| --- | --- |
| `serv_name` | Nombre del servidor (debe coincidir con el hostname real si se ejecuta desde ahí, y con el nombre usado en `ssh` para los túneles). |
| `plant` | Nombre de la planta a la que pertenece este servidor. |
| `activate` | `1` para revisar este servidor, `0` para ignorarlo sin borrarlo del archivo. |
| `cam_activate` | *(opcional)* `true` = revisar solo las cámaras marcadas como activas en el YAML que entrega el servicio IA; `false` o ausente = revisar todas, sin filtrar. |
| `type` | `remote` (dirección IP y proxy directo) o `tunnels` (requiere túnel SSH para alcanzar el servidor). |
| `addresses.local` / `.cameras` / `.zerotier` | Las tres formas de alcanzar el servidor; se prueban en ese orden (zerotier → local → cámaras), se usa la primera que responda al ping. |
| `proxy_port` | Puerto del proxy en el servidor remoto. |
| `ia_ports` | Uno o varios puertos donde corre el servicio de IA en ese servidor — se revisan todos, cada uno con su propio lote de cámaras. |

**Nombre del archivo → `client_id`:** el programa descubre automáticamente todos los `*.yaml` directamente dentro de `conf/plants/` (no busca en subcarpetas) y deriva un `client_id` del nombre de archivo (sin extensión): por cada segmento separado por `_` sube a mayúscula solo la primera letra si está en minúscula, sin tocar el resto — así conserva mayúsculas internas intencionales. Convención: CamelCase con `_` como separador de palabra, sin espacios (para que funcione igual en Ubuntu). Ejemplos:

| Archivo | `client_id` (= carpeta de resultados, `RESULT_PATH/<client_id>/`) |
| --- | --- |
| `Api_Manzanillo.yaml` | `Api_Manzanillo` |
| `api_manzanillo.yaml` | `Api_Manzanillo` |
| `AbInBev.yaml` | `AbInBev` (no se convierte a `Abinbev`) |

Un YAML que no deba revisarse desde esta máquina (ej. el de otro entorno, guardado solo de referencia) va en cualquier subcarpeta de `conf/plants/` — el descubrimiento no es recursivo, así que nunca se toca.

## Uso

```bash
# Revisar TODOS los clientes/plantas activos
pipenv run python main.py --plant all
# (equivalente: pipenv run python main.py --client all)

# Revisar un solo cliente completo (todos sus servidores)
pipenv run python main.py --client Api_Manzanillo

# Revisar una planta específica (busca en todos los clientes descubiertos)
pipenv run python main.py --plant nombre_planta

# Revisar un servidor específico (busca en todos los clientes descubiertos)
pipenv run python main.py --server nombre_servidor
```

`--plant`, `--server` y `--client` son mutuamente excluyentes — se usa uno solo. La diferencia entre `--plant`/`--server` y `--client`: los dos primeros filtran por el campo `plant`/`serv_name` de cada servidor sin importar en qué archivo esté; `--client` revisa TODOS los servidores de un archivo puntual, sin importar a qué planta pertenezcan.

## Qué hace el programa

Por cada servidor activo:

1. Hace ping probando IP de Zerotier → local → cámaras, en ese orden, y usa la primera que responda.
2. Si el servidor es `type: tunnels`, abre el túnel SSH necesario antes de continuar.
3. Por cada puerto en `ia_ports`, lee el YAML de cámaras que entrega el servicio de IA de ese servidor.
4. Por cada cámara activa (varias en paralelo, según `MAX_CAMERA_WORKERS`):
   - Verifica que el puerto 80 de la cámara responda.
   - Si responde, descarga: la imagen procesada por la IA del servidor, la imagen directa de la cámara, y su configuración — cada una según el formato propio de la marca de esa cámara.
5. Al terminar el servidor, cierra los túneles que haya abierto.
6. Al terminar toda la corrida (varios servidores), genera el resumen final.

## Marcas de cámara soportadas

Axis, Hikvision, Vivotek y Dahua — cada una con su propio módulo en `conf/cameras/`, registrado en `CAMERA_HANDLERS` (`cameras.py`).

**Para agregar una marca nueva:**

1. Crear `conf/cameras/<marca>.py` con dos funciones, `<Marca>CamImage` y `<Marca>CamConf`, con la misma firma que las ya existentes: `(session, camera_ip, username, password, proxy_ip, proxy_port, channel=1, plant=None, server=None)`.
2. Agregar la entrada en `CAMERA_HANDLERS` (`cameras.py`).
3. Agregar el patrón de detección de esa marca en `resolve_brand()` (`file_processor.py`) — es un mapeo aparte (URL del video → marca) que no vive en el registro; sin este paso, esa marca nunca se identifica y nunca llega a usar el manejador del paso 2.

## Qué resultados entrega

Todo queda bajo `RESULT_PATH`, organizado por cliente, fecha, planta y servidor — un cliente nunca mezcla sus resultados con los de otro:

```text
RESULT_PATH/
  <client_id>/                       <- uno por archivo de conf/plants/*.yaml
    09- Septiembre/
      170926/                        <- fecha (ddmmaa)
        resumen_17-09-2026.log       <- resumen de ESTE cliente en esta corrida
        NOMBRE_PLANTA/
          NOMBRE_SERVIDOR/
            NOMBRE_SERVIDOR.log      <- log detallado de ese servidor
            alias_camara.jpg         <- imagen directa de la cámara
            alias_camara_ai.jpg      <- imagen procesada por la IA
            alias_camara.json        <- configuración de la cámara
```

El **resumen** (`resumen_dd-mm-aaaa.log`) es el primer lugar para revisar una corrida. Se genera uno por cliente (una corrida con `--client all`/`--plant all` que toca varios clientes genera un resumen por cada uno, no uno mezclado), y solo cuando ese cliente tuvo más de un servidor revisado — para un solo servidor, su propio log ya es suficiente. Tiene tres partes:

1. Totales generales (servidores/cámaras revisados, completos, con falla).
2. **`DETALLE POR SERVIDOR`**: una línea por cada servidor revisado, siempre presente — a diferencia del resto del resumen, que solo lista excepciones, aquí ningún servidor puede "desaparecer" por estar perfecto ni por estar caído:
   - `[OK]` — todas sus cámaras activas completaron sin ningún error.
   - `[CON FALLAS]` — al menos una cámara tuvo algún error (el número indica cuántas de cuántas completaron).
   - `[SIN CONEXIÓN]` — el servidor mismo nunca respondió, no se revisó ninguna cámara.
   - `[SIN YAML]` — el servidor sí respondió, pero no se pudo leer el listado de cámaras en ningún puerto IA (distinto de `[SIN CONEXIÓN]`: aquí sí hubo contacto con el servidor, solo falló ese paso puntual).

   Tanto `[SIN CONEXIÓN]` como `[SIN YAML]` se muestran como `-/- cámaras completas` — el estado ya dice el motivo general, y el detalle exacto del error está en el log de esa planta, no se repite aquí.
3. `DETALLE POR PLANTA - CÁMARAS CON FALLAS`: qué cámara falló y en qué paso (solo aparece si hubo al menos una falla). Un bloque por servidor (si una planta tiene varios servidores, van separados por una línea `====`); dentro de cada servidor, las cámaras se ordenan primero por tipo de falla (Puerto 80 → Imagen IA → Imagen cámara → Configuración) y luego alfabéticamente por alias.

Tanto el orden de `DETALLE POR SERVIDOR` como el de las plantas/servidores en `DETALLE POR PLANTA` siguen la estrategia configurada en `LOG_SORT_STRATEGY`.

### Agregar una estrategia de orden nueva (para un cliente con otra convención de nombres)

Hoy existen dos estrategias en `sort_strategies.py`: `alphabetical` (por nombre completo) y `numeric_suffix` (por el número al final del nombre del servidor). Si un cliente nuevo necesita un criterio distinto:

1. Escribir una función en `sort_strategies.py` que reciba `serv_name` y devuelva una clave de orden (ver `_numeric_suffix_key`/`_alphabetical_key` como ejemplo).
2. Agregarla al diccionario `SORT_STRATEGIES` con un nombre corto.
3. Poner ese nombre en `LOG_SORT_STRATEGY` en el `.env` de ese cliente/entorno.

No hace falta tocar `file_processor.py` ni ningún otro archivo — `write_summary()` ya usa la estrategia que esté configurada.

## Cómo leer el log

Cada línea sigue el patrón `[hora] [nivel] alias: proceso  descripción  [código]` (el nombre del proceso — `Puerto 80`, `Imagen IA`, `Imagen cámara`, `Configuración` — siempre queda explícito, no solo el código), coloreado según el nivel:

- **Verde (`INFO`):** éxito, o líneas estructurales (separadores, encabezados).
- **Amarillo (`WARNING`):** la cámara terminó bien, pero tardó más de `CAM_TIME_THRESHOLD` — solo aviso, no indica una falla.
- **Rojo (`ERROR`):** falla real — el código entre corchetes (`[111]`, `[790]`, etc.) identifica el tipo exacto; el catálogo completo está en `config.STATUS_MESSAGES`.

El log de cada servidor se escribe en vivo mientras corre (así queda un rastro aunque el programa se interrumpa a medio camino), pero justo después de terminar de revisar sus cámaras, la sección de cámaras se reescribe limpia: cada cámara en un bloque contiguo (antes podían intercalarse entre sí, porque varias corren en paralelo), ordenadas alfabéticamente por alias y con columnas alineadas. El encabezado, los túneles y la lectura del YAML no se tocan.

## Pruebas automatizadas

```bash
pipenv run pytest
```

Cubre funciones puras (sin red): detección de marca, extracción de credenciales de una URL, parseo de configuración de cada marca, clasificación de códigos de estado, validación de campos requeridos de un servidor, reintentos de `Cam_Config()`, verificación de que un túnel SSH apunte al destino correcto, y el orden/contenido del resumen (`DETALLE POR SERVIDOR`/`DETALLE POR PLANTA`, estrategias de `sort_strategies.py`).
