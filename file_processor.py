from colorama import init, Fore, Style
from datetime import datetime
import requests
import config
import locale
import json
import yaml
import os
import re

init(autoreset=True)


def InfoPlant(plant, server):                                               #---------- PROBADO ----------#
    try:
        # Obtener ruta del archivo YAML relativa al script
        current_dir = os.path.dirname(os.path.abspath(__file__))
        path_file = os.path.join(current_dir, 'conf', 'plants', 'plants.yaml')

        # Intentar abrir el archivo
        try:
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
        
    except Exception:
        return (905, {})
        

def InfoCam_url(url):                                                       #---------- PROBADO ----------#
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
        print(f"Error al extraer información de la URL {url}: {str(e)}")
    
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
    

def colorize(output):                                                       #---------- PROBADO ----------#
    if "SUCCESS" in output:
        return output.replace("SUCCESS", Fore.GREEN + "SUCCESS" + Style.RESET_ALL)
    elif "WARNING" in output:
        return output.replace("WARNING", Fore.YELLOW + "WARNING" + Style.RESET_ALL)
    elif "ERROR" in output:
        return output.replace("ERROR", Fore.RED + "ERROR" + Style.RESET_ALL)
    return output


def log_processor(plant, server, status_code, add_timestamp: bool):         #---------- PROBADO ----------#
    if isinstance(status_code, str):
        message = status_code
    else:
        message = config.STATUS_MESSAGES.get(
            status_code, 
            f"[ERROR]   Unknown status code     [{status_code}]"
        )
        
    result_dir = dirs_path(plant, server)
    if plant is None:
        plant = "error"
    server_name = server.upper() if server else plant.upper()
    log_file = os.path.join(result_dir, f"{server_name}.log")
    file_exists = os.path.isfile(log_file)
    
    with open(log_file, 'a') as f:
        if not file_exists:
            date_now = datetime.now()
            header = f"{plant.upper()} - {date_now.strftime('%d/%m/%Y - %H:%M')}\n"
            f.write(header)
            print(header.strip())
        
        if add_timestamp:
            timestamp = datetime.now().strftime('%H:%M:%S')
            output = f"[{timestamp}] {message}"
        else:
            output = message
        
        # Archivo sin colores
        f.write(output + "\n")
        
        # Pantalla con solo la palabra coloreada
        print(colorize(output))


def dirs_path(plant=None, server=None):                                     #---------- PROBADO ----------#
    locale.setlocale(locale.LC_TIME, 'es_MX.UTF-8')
    date_now = datetime.now()
    month_dir = f"{date_now.month:02d}- {date_now.strftime('%B').capitalize()}"
    text_date = date_now.strftime("%d%m%y")

    # Construir partes de la ruta solo si tienen valor
    parts = [config.RESULT_PATH, month_dir, text_date]
    if plant:
        parts.append(plant)
    if server:
        parts.append(server)

    result_path = os.path.join(*parts)
    os.makedirs(result_path, exist_ok=True)
    return result_path


def read_yaml(url):                                                         #---------- PROBADO ----------#
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
        
    except Exception:
        return 413, None
    

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