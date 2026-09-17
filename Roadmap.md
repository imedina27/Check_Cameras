# Roadmap — Check Cameras V2

Basado en la revisión de `Check_Cam_V1`. Enfoque: **refactor incremental** — mismo propósito y arquitectura general, corrigiendo errores, optimizando el código y actualizando módulos clave. Sin rediseño mayor (sin dashboard/DB/alertas por ahora).

Orden sugerido: primero corregir lo que está roto o es frágil, luego optimizar rendimiento, luego modernizar módulos.

---

## Fase 0 — Preparación del proyecto

- [ ] Copiar todos los archivos de `Check_Cam_V1` a la raíz del proyecto (`Check_Cameras`), dejando `Check_Cam_V1` como carpeta de referencia.
- [ ] Hacer commit del proyecto.

---

## Fase 1 — Corrección de errores de programación

- [ ] **`main.py` ignora los argumentos reales de CLI.** `sys.argv` se sobreescribe de forma fija a `--plant all` ([main.py:52-54](Check_Cam_V1/main.py#L52-L54)), dejando el `argparse` real sin efecto. Quitar el override y dejar que el script use los argumentos reales.
- [ ] **Gestión de túneles SSH no funciona en Windows.** `system_processor.py` usa `ss -tulpn`, `os.kill`, `signal.SIGTERM/SIGKILL` y `pkill`, herramientas de Unix, mientras que `ping()` sí distingue Windows/Linux. Definir soporte real multiplataforma (o documentar explícitamente que el tunneling requiere ejecutarse desde un host Unix).
- [ ] **`locale.setlocale(locale.LC_TIME, 'es_MX.UTF-8')` puede tronar la ejecución completa** si el locale no está instalado en la máquina ([file_processor.py:188](Check_Cam_V1/file_processor.py#L188)). Reemplazar por formateo de fecha en español sin depender del locale del sistema (diccionario de meses o `babel`).
- [ ] **Sin manejo de claves faltantes en YAML.** `CheckServer()` accede directo a `dat_server['addresses']['local']`, `dat_server['ia_ports']`, etc. Un YAML de planta incompleto tumba toda la corrida en vez de solo esa planta/servidor. Agregar validación con mensajes claros y continuar con el resto.
- [ ] **Credenciales de cámara en texto plano en memoria** (extraídas por regex desde la URL en `InfoCam_url`). Revisar que no queden expuestas en excepciones/logs no controlados.
- [ ] Revisión general de excepciones genéricas (`except Exception`) que ocultan la causa real del error — acotar a las excepciones esperadas y loguear el detalle.

## Fase 2 — Optimización de código

- [ ] **Procesamiento secuencial es el mayor cuello de botella.** Servidores y cámaras se revisan uno por uno. Paralelizar con `concurrent.futures.ThreadPoolExecutor` (o `asyncio` + `httpx`) a nivel de servidor y de cámara.
- [ ] **Reutilizar sesiones HTTP** (`requests.Session()`) en vez de abrir una conexión nueva por cada request a cámara/servicio IA — reduce overhead de TCP/TLS handshake por cámara.
- [ ] **Revisar acumulación de timeouts:** con reintentos en ping, puerto 80, imagen y config, un solo servidor caído puede consumir varios minutos antes de continuar. Definir un timeout máximo por servidor/planta.
- [ ] Evitar trabajo repetido en `dirs_path()` (llama `os.makedirs` y recalcula la fecha en cada log individual).

## Fase 3 — Actualización de módulos

- [ ] **Reemplazar el despacho de marca por if/elif** en `cameras.py` (`Cam_Image`, `Cam_Config`) por un registro (dict marca → funciones/clase), para agregar una marca nueva sin tocar múltiples bloques.
- [ ] **Unificar gestión de dependencias.** Hoy conviven `Pipfile` y `requirements.txt` con riesgo de drift; `requirements.txt` además mezcla herramientas de lint (`pylint`, `astroid`, `isort`) con dependencias de producción. Definir una sola fuente de verdad.
- [ ] **Logging estructurado.** Sustituir el logging manual a archivo + `print()` coloreado por el módulo estándar `logging` (niveles, rotación, formato consistente), manteniendo el output coloreado en consola si se desea.
- [ ] **Resumen final de ejecución.** Al terminar `CheckAll`/`CheckPlant`, generar un resumen (cámaras OK/falla por planta) en vez de solo dejarlo en el log línea por línea.
- [ ] **Pruebas automatizadas básicas.** Los comentarios `#---------- PROBADO ----------#` indican verificación manual. Agregar tests unitarios (pytest) al menos para: `resolve_brand`, `InfoCam_url`, `dic_to_json`/`txt_to_json`, y el manejo de status codes.
- [ ] Revisar duplicidad `plants.yaml` vs `plants_abinbev.yaml` — confirmar cuál es la fuente activa y documentar el propósito del otro (¿plantilla genérica?).

---

## Fuera de alcance para V2 (posible V3)
- Dashboard web / interfaz gráfica.
- Base de datos histórica de resultados.
- Alertas automáticas (correo/Slack/Teams) ante fallas.
