import requests
import urllib.parse
import config
from file_processor import log_processor


def AxisCamImage(session, camera_ip, username, password, proxy_ip, proxy_port, channel=1, plant=None, server=None, result_path=None):
    password = urllib.parse.unquote(password)
    
    img_urls = [
        f"http://{camera_ip}/axis-cgi/jpg/image.cgi?camera={channel}"
    ]

    headers = {
            "Content-Type": "image/jpeg"
        }

    if proxy_ip and proxy_port:
        proxies = {
            "http": f"http://{proxy_ip}:{proxy_port}",
            "https": f"http://{proxy_ip}:{proxy_port}"
        }
    else:
        proxies = {}

    auth = requests.auth.HTTPDigestAuth(username, password)

    try:
        for img_url in img_urls:
            try:
                response = session.get(img_url, headers=headers, auth=auth,
                                      proxies=proxies, timeout=config.IMAGE_TIMEOUT)
                response.raise_for_status()
                return response.content
            except requests.exceptions.HTTPError:
                continue

        return 640

    except requests.exceptions.Timeout:
        log_processor(plant, server, f"[ERROR] {camera_ip}: timeout al descargar imagen", result_path=result_path)
        return 611

    except requests.exceptions.ConnectionError as e:
        log_processor(plant, server, f"[ERROR] {camera_ip}: error de conexión al descargar imagen: {e}", result_path=result_path)
        return 620

    except requests.exceptions.RequestException as e:
        log_processor(plant, server, f"[ERROR] {camera_ip}: error inesperado al descargar imagen: {e}", result_path=result_path)
        return 690


def AxisCamConf(session, camera_ip, username, password, proxy_ip, proxy_port, channel=1, plant=None, server=None, result_path=None):
    # Decodificar la contraseña si contiene caracteres codificados como %40
    password = urllib.parse.unquote(password)
        
    grl_url = f"http://{camera_ip}/axis-cgi/param.cgi?action=list&group=root"

    headers = {
        "Content-Type": "application/json"
    }

    if proxy_ip and proxy_port:
        proxies = {
            "http": f"http://{proxy_ip}:{proxy_port}",
            "https": f"http://{proxy_ip}:{proxy_port}"
        }
    else:
        proxies = {}
    
    auth = requests.auth.HTTPDigestAuth(username, password)

    json_conf = {}
    
    try:
        # Usar timeout configurable para descarga de configuración
        response = session.get(grl_url, headers=headers, auth=auth,
                              proxies=proxies, timeout=config.IMAGE_TIMEOUT)
        response.raise_for_status()
        json_conf = dic_to_json(response.text)
    
    except requests.exceptions.Timeout:
        log_processor(plant, server, f"[ERROR] {camera_ip}: timeout al descargar configuración", result_path=result_path)
        return 711

    except requests.exceptions.RequestException as e:
        log_processor(plant, server, f"[ERROR] {camera_ip}: error al descargar configuración: {e}", result_path=result_path)
        return 790

    return json_conf


def dic_to_json(text):
    # Convierte un diccionario Plano separado por puntos en un json

    config_dict = {}

    for line in text.split('\n'):
        line = line.strip()
        if "=" not in line:
            continue
        # partition (no split) porque el VALOR puede traer su propio "="
        # (ej. root.Network.RTP.R0.AlwaysMulticastProfile=videocodec=h264,
        # o root.PTZ.Preset.P0.Position.P1.Data=pan=0:tilt=0:zoom=1) —
        # con split("=") esas líneas se perdían enteras, en silencio.
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        key_parts = key.split(".")[1:]  # Excluir "root"
        if not key_parts:
            continue
        current_dict = config_dict

        for part in key_parts[:-1]:
            if part not in current_dict:
                current_dict[part] = {}
            current_dict = current_dict[part]

        current_dict[key_parts[-1]] = value

    return config_dict