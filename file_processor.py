from colorama import init, Fore, Style
from datetime import datetime
import requests
import logging
import config
import json
import yaml
import os
import re
import threading

init(autoreset=True)

MESES_ES = {
    1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
    5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
    9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'
}

# Carpetas ya confirmadas/creadas en esta corrida, para no repetir llamadas
# al sistema de archivos (os.makedirs) en cada línea de log.
_dirs_ensured = set()

# Loggers por archivo de log (uno por planta/servidor), para no reconfigurar
# handlers en cada llamada.
_server_loggers = {}

# Candado para crear loggers/directorios de forma segura entre hilos (varias
# cámaras del mismo servidor pueden loguear por primera vez casi al mismo
# tiempo al paralelizar) — sin esto, dos hilos podrían crear el mismo logger
# dos veces y duplicar los manejadores (líneas repetidas en el log).
_logger_lock = threading.Lock()

_LOG_FORMAT = "[%(asctime)s] %(levelname)-7s %(message)s"
_LOG_DATEFMT = "%H:%M:%S"

# Nivel para líneas puramente estructurales (separadores, "Camera: X IP: Y",
# "Ping to Server..."): se muestran como "INFO" en el texto, igual que hoy,
# pero SIN color — así el verde queda reservado a éxitos reales y el rojo a
# errores reales, y se distingue de un vistazo el cambio de servidor/cámara.
STRUCTURE_LEVEL = 15
logging.addLevelName(STRUCTURE_LEVEL, "INFO")

_LEVEL_COLORS = {
    logging.INFO: Fore.GREEN,
    logging.WARNING: Fore.YELLOW,
    logging.ERROR: Fore.RED,
}


class _ColorConsoleFormatter(logging.Formatter):
    def format(self, record):
        base = super().format(record)
        color = _LEVEL_COLORS.get(record.levelno, "")
        return f"{color}{base}{Style.RESET_ALL}" if color else base


def InfoPlant(plant, server):                                               #---------- PROBADO ----------#
    try:
        # Obtener ruta del archivo YAML relativa al script
        current_dir = os.path.dirname(os.path.abspath(__file__))
        path_file = os.path.join(current_dir, 'conf', 'plants', config.PLANTS_FILE)

        # Intentar abrir el archivo
        try:
            print(f"[INFO] Cargando configuración de plantas: {config.PLANTS_FILE}")
            with open(path_file, 'r', encoding='utf-8') as archivo:
                content = yaml.safe_load(archivo)
        except FileNotFoundError:
            return (903, {})
        except yaml.YAMLError:
            return (904, {})
        
        servers = content.get('servers', [])

        active_servers = {}
        for serv_nam in servers:
            if serv_nam.get('activate') == 1:
                serv_name = serv_nam.get('serv_name')
                active_servers[serv_name] = serv_nam
        
        # Si no hay servidores activos
        if len(active_servers) == 0:
            return (901, {})
                
        # Caso: Retornar todos los servidores activos
        if plant == 'ALL':
            return (900, active_servers)

        # Caso: Buscar una planta
        if plant is not None:
            result = {}
            for serv_name, dat_server in active_servers.items():
                if dat_server.get('plant') == plant:
                    result[serv_name] = dat_server
            
            if len(result) == 0:
                return (901, {})
            
            return (900, result)
        
        else:
            result = {}
            for serv_name, dat_server in active_servers.items():
                if dat_server.get('serv_name') == server:
                    result[serv_name] = dat_server
        
            if len(result) == 0:
                return (901, {})

            return (900, result)
        
    except Exception as e:
        print(f"[ERROR] Fallo inesperado leyendo la configuración de plantas: {e}")
        return (905, {})
        

def mask_credentials(url):                                                  #---------- PROBADO ----------#
    # Enmascara usuario y contraseña embebidos en una URL (ej. rtsp://user:pass@ip)
    # para que nunca se impriman/logueen credenciales en texto plano.
    if not url:
        return url
    return re.sub(r'(://)[^:/@]+:[^/]*@', r'\1***:***@', url)


def InfoCam_url(url, plant=None, server=None):                              #---------- PROBADO ----------#
    # Establecer valores por defecto
    info = {
        'user': '',
        'password': '',
        'ip': '',
        'brand': resolve_brand(url),
        'channel': 1
    }
    
    try:
        # Patrón para extraer usuario, contraseña e IP (soporta rtsp, http, https)
        patron = r'(?:rtsp|https?)://([^:]+):([^@]+)@([^:/]+)'
        match = re.search(patron, url)
        
        if match:
            info['user'] = match.group(1)
            info['password'] = match.group(2)
            info['ip'] = match.group(3)
        else:
            # Intentar con formato alternativo (sin contraseña)
            patron_simple = r'(?:rtsp|https?)://([^@]+)@([^:/]+)'
            match_simple = re.search(patron_simple, url)
            
            if match_simple:
                info['user'] = match_simple.group(1)
                info['ip'] = match_simple.group(2)
            else:
                # Último intento: solo obtener la IP
                patron_ip = r'(?:rtsp|https?)://([^:/]+)'
                match_ip = re.search(patron_ip, url)
                
                if match_ip:
                    info['ip'] = match_ip.group(1)

        # Extraer el canal (camera=N) del query string si existe
        # Aplica solo a cámaras multi-sensor (ej. Axis Q3708, Q3819)
        # Si no se encuentra, el default 'channel': 1 se mantiene
        
        patron_channel = r'[?&]camera=(\d+)'
        match_channel = re.search(patron_channel, url)
        if match_channel:
            info['channel'] = int(match_channel.group(1))
                    
    except Exception as e:
        log_processor(plant, server, f"[ERROR] Error al extraer información de la URL {mask_credentials(url)}: {str(e)}")

    return info


def resolve_brand(url):                                                     #---------- PROBADO ----------#
    if not url:
        return "DESCONOCIDO"
    
    # Convertir a minúsculas para hacer la comparación case-insensitive
    url_lower = url.lower()
    
    if "axis" in url_lower:
        return "AXIS"
    elif "streaming/channels" in url_lower:
        return "HIKVISION"
    elif "/media2/stream" in url_lower:
        return "VIVOTEK"
    elif "/cam/realmonitor" in url_lower:
        return "DAHUA"
    else:
        return "DESCONOCIDO"
    

def _get_server_logger(log_file, plant_label):
    """Devuelve (creándolo si hace falta) el logger para este archivo de log:
    un FileHandler (texto plano) + un StreamHandler coloreado por nivel.
    Seguro para hilos: varias cámaras del mismo servidor pueden pedirlo por
    primera vez casi al mismo tiempo al paralelizar."""
    if log_file in _server_loggers:
        return _server_loggers[log_file]

    with _logger_lock:
        # Volver a revisar: otro hilo pudo haberlo creado mientras esperábamos el candado
        if log_file in _server_loggers:
            return _server_loggers[log_file]

        file_is_new = not os.path.isfile(log_file)

        logger = logging.getLogger(f"check_cameras.{log_file}")
        logger.setLevel(STRUCTURE_LEVEL)
        logger.propagate = False

        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_LOG_DATEFMT))
        logger.addHandler(file_handler)

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(_ColorConsoleFormatter(_LOG_FORMAT, datefmt=_LOG_DATEFMT))
        logger.addHandler(console_handler)

        if file_is_new:
            header = f"{plant_label.upper()} - {datetime.now().strftime('%d/%m/%Y - %H:%M')}"
            file_handler.stream.write(header + "\n")
            file_handler.stream.flush()
            print(header)

        _server_loggers[log_file] = logger
        return logger


def log_processor(plant, server, status_code, prefix="", proceso=None):     #---------- PROBADO ----------#
    result_dir = dirs_path(plant, server)
    plant_label = plant if plant is not None else "error"
    server_name = server.upper() if server else plant_label.upper()
    log_file = os.path.join(result_dir, f"{server_name}.log")

    logger = _get_server_logger(log_file, plant_label)

    # Línea vacía: solo da espacio visual, no es un evento a loguear.
    if isinstance(status_code, str) and status_code == "":
        for handler in logger.handlers:
            handler.acquire()
            try:
                handler.stream.write("\n")
                handler.flush()
            finally:
                handler.release()
        return

    if isinstance(status_code, str):
        logger.log(STRUCTURE_LEVEL, prefix + status_code)
        return

    raw = config.STATUS_MESSAGES.get(status_code, f"Unknown status code [{status_code}]")

    if proceso:
        # Formato [ALIAS: PROCESO  DESCRIPCIÓN  [CODIGO]] — el proceso queda
        # explícito en la línea (antes solo se sabía la cámara, no cuál de
        # los 4 pasos falló, ya que varios códigos de error se comparten
        # entre procesos, ej. 611/711 son "Timed out" tanto en Imagen como
        # en Configuración).
        descripcion, codigo = _status_parts(status_code)
        if raw.startswith("[SUCCESS]"):
            descripcion = "OK"
        message = f"{prefix}{proceso:<16}{descripcion:<20}[{codigo}]"
    else:
        message = prefix + status_text(status_code)

    if raw.startswith("[WARNING]"):
        logger.warning(message)
    elif raw.startswith("[ERROR]"):
        logger.error(message)
    else:
        logger.info(message)


def status_text(status_code):                                              #---------- PROBADO ----------#
    """Texto legible de un status_code, sin el prefijo [SUCCESS]/[WARNING]/[ERROR]."""
    raw = config.STATUS_MESSAGES.get(status_code, f"Unknown status code [{status_code}]")
    return re.sub(r"^\[(SUCCESS|WARNING|ERROR)\]\s*", "", raw).strip()


def _status_parts(status_code):                                            #---------- PROBADO ----------#
    """(descripción, código) de un status_code, separando el texto del
    número entre corchetes — para armar líneas con el proceso explícito."""
    texto = status_text(status_code)
    match = re.match(r"^(.*?)\s*\[(\d+)\]$", texto)
    if match:
        return match.group(1).strip(), match.group(2)
    return texto, str(status_code)


def is_success_code(status_code):                                          #---------- PROBADO ----------#
    return config.STATUS_MESSAGES.get(status_code, "").startswith("[SUCCESS]")


def log_camera_time(plant, server, alias, elapsed_seconds):                 #---------- PROBADO ----------#
    """Registra cuánto tardó el proceso completo de una cámara (Cam_Up +
    Cam_AI_Image + Cam_Image + Cam_Config): verde si quedó dentro de
    config.CAM_TIME_THRESHOLD, amarillo si lo excedió. Es solo visibilidad,
    no cancela ni omite nada."""
    result_dir = dirs_path(plant, server)
    plant_label = plant if plant is not None else "error"
    server_name = server.upper() if server else plant_label.upper()
    log_file = os.path.join(result_dir, f"{server_name}.log")

    logger = _get_server_logger(log_file, plant_label)
    mensaje = f"{alias}: Tiempo de proceso {elapsed_seconds:.2f}s"

    if elapsed_seconds <= config.CAM_TIME_THRESHOLD:
        logger.info(mensaje)
    else:
        logger.warning(mensaje)


def dirs_path(plant=None, server=None):                                     #---------- PROBADO ----------#
    date_now = datetime.now()
    month_dir = f"{date_now.month:02d}- {MESES_ES[date_now.month]}"
    text_date = date_now.strftime("%d%m%y")

    # Construir partes de la ruta solo si tienen valor
    parts = [config.RESULT_PATH, month_dir, text_date]
    if plant:
        parts.append(plant)
    if server:
        parts.append(server)

    result_path = os.path.join(*parts)
    if result_path not in _dirs_ensured:
        os.makedirs(result_path, exist_ok=True)
        _dirs_ensured.add(result_path)
    return result_path


def read_yaml(url, plant=None, server=None):                                #---------- PROBADO ----------#
    """
    Lee un archivo YAML desde una URL HTTP.
    
    Args:
        url (str): URL completa del archivo YAML (ej: http://192.168.192.193:12046/cameras)
        timeout (int): Tiempo máximo de espera en segundos (default: 5)
    
    Returns:
        tuple: (status_code, data)
            - status_code (int): 
                400 - Lectura exitosa
                410 - URL no accesible / Connection error
                411 - Timeout
                412 - Formato YAML inválido
                413 - Error HTTP (404, 500, etc.)
                414 - URL vacía
                415 - Error inesperado (no HTTP/timeout/YAML)
            - data (dict|None): Datos del YAML si es exitoso, None si hay error
    """
    timeout = config.YAML_TIMEOUT
    # Validación inicial
    if not url or url == '':
        return 414, None
    
    try:
        # Realizar petición HTTP GET
        response = requests.get(url, timeout=timeout)
        
        # Verificar si la respuesta fue exitosa (status 200-299)
        if response.status_code == 200:
            # Parsear el contenido YAML
            data = yaml.safe_load(response.text)
            return 400, data
        else:
            # Error HTTP (404, 500, etc.)
            return 413, None
            
    except requests.exceptions.Timeout:
        return 411, None
        
    except requests.exceptions.ConnectionError:
        return 410, None
        
    except yaml.YAMLError:
        return 412, None

    except Exception as e:
        log_processor(plant, server, f"[ERROR] Error inesperado leyendo YAML desde {url}: {e}")
        return 415, None
    

def save_img(cam_img, plant, serv_name, cam_name, ai):                      #---------- PROBADO ----------#
    plant_dir = dirs_path(plant, serv_name)
    if ai:
        path_img = os.path.join(plant_dir, f"{cam_name}_ai.jpg")
    else:
        path_img = os.path.join(plant_dir, f"{cam_name}.jpg")
    
    # Guarda la imagen en el directorio correcto
    if cam_img:
        if isinstance(cam_img, int):
            return cam_img
        else:
            try:
                with open(path_img, "wb") as file:
                    file.write(cam_img)
                if ai:
                    cam_img = 600
                else:
                    cam_img = 601
                return cam_img
            except TypeError as e:
                cam_img = 640
                return cam_img
    

def save_json(cam_json, plant, serv_name, cam_name):                        #---------- PROBADO ----------#

    plant_dir = dirs_path(plant, serv_name)
    file_path = os.path.join(plant_dir, f"{cam_name}.json")

    with open(file_path, "w", encoding="utf-8") as archivo:
        json.dump(cam_json, archivo, indent=4)
        return 900


def write_summary(server_results):                                         #---------- PROBADO ----------#
    """Genera el resumen de una corrida con varios servidores (--plant all o
    CheckPlant con varios servidores encontrados): totales de servidores/
    cámaras, y el detalle por planta de las cámaras que fallaron y en qué.
    Se guarda como resumen_dd-mm-aaaa.log en la carpeta del día."""
    day_dir = dirs_path()
    date_str = datetime.now().strftime("%d-%m-%Y")
    summary_file = os.path.join(day_dir, f"resumen_{date_str}.log")

    servers_ok = [r for r in server_results if r["problem"] is None]
    servers_problem = [r for r in server_results if r["problem"] is not None]

    all_cameras = [cam for r in server_results for cam in r["cameras"]]
    cameras_ok = [c for c in all_cameras if c["complete"]]
    cameras_failed = [c for c in all_cameras if not c["complete"]]

    lines = []
    lines.append("=" * 42)
    lines.append("RESUMEN DE EJECUCIÓN")
    lines.append("=" * 42)
    lines.append(f"Servidores revisados: {len(server_results)} ({len(servers_ok)} OK, {len(servers_problem)} con problemas)")
    lines.append(f"Cámaras revisadas: {len(all_cameras)}")
    lines.append(f"  - Completas (imagen IA + imagen + config): {len(cameras_ok)}")
    lines.append(f"  - Con al menos una falla: {len(cameras_failed)}")
    if servers_problem:
        lines.append("Servidores con problemas:")
        for r in servers_problem:
            lines.append(f"  - {r['serv_name']} ({r['plant']}): {r['problem']}")
    lines.append("=" * 42)

    if cameras_failed:
        lines.append("")
        lines.append("DETALLE POR PLANTA - CÁMARAS CON FALLAS")
        by_plant = {}
        for r in server_results:
            for cam in r["cameras"]:
                if not cam["complete"]:
                    by_plant.setdefault(r["plant"], []).append((r["serv_name"], cam))
        for plant_name in sorted(by_plant):
            lines.append(f"{plant_name}:")
            entries = by_plant[plant_name]

            # Alinear columnas dentro de cada planta según el nombre/IP más largo
            tag_width = max(len(f"[{serv_name}] {cam['alias']}") for serv_name, cam in entries)
            ip_width = max(len(cam['ip']) for _, cam in entries)

            for serv_name, cam in entries:
                tag = f"[{serv_name}] {cam['alias']}".ljust(tag_width)
                ip = cam['ip'].ljust(ip_width)
                fails = "; ".join(cam["failures"])
                lines.append(f"  - {tag}  {ip}  {fails}")

    text = "\n".join(lines)
    with open(summary_file, "w", encoding="utf-8") as f:
        f.write(text + "\n")
    print(text)
    return summary_file