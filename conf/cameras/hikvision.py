import requests
import xmltodict
import urllib.parse
import config
import xml.parsers.expat
from file_processor import log_processor


def HikvCamImage(session, camera_ip, username, password, proxy_ip, proxy_port, channel=1, plant=None, server=None):
    password = urllib.parse.unquote(password)
    
    img_urls = [
        f"http://{camera_ip}/ISAPI/Streaming/channels/1/picture"
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
        log_processor(plant, server, f"[ERROR] {camera_ip}: timeout al descargar imagen")
        return 611

    except requests.exceptions.ConnectionError as e:
        log_processor(plant, server, f"[ERROR] {camera_ip}: error de conexión al descargar imagen: {e}")
        return 620

    except requests.exceptions.RequestException as e:
        log_processor(plant, server, f"[ERROR] {camera_ip}: error inesperado al descargar imagen: {e}")
        return 690


def HikvCamConf(session, camera_ip, username, password, proxy_ip, proxy_port, channel=1, plant=None, server=None):
    # Decodificar la contraseña si contiene caracteres codificados como %40
    password = urllib.parse.unquote(password)

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
    get_confs = [
        'System/deviceInfo',
        'System/Network/interfaces/1',
        'Image/channels/1',
        'Streaming/channels/101/',
        'System/time',
        'Security/users',
        'System/capabilities',
    ]

    json_conf = {}

    try:
        for get_conf in get_confs:
            grl_url = f'http://{camera_ip}/ISAPI/{get_conf}'
            
            # Usar timeout configurable para cada petición de configuración
            response = session.get(grl_url, headers=headers, auth=auth,
                                  proxies=proxies, timeout=config.CONF_TIMEOUT)
            response.raise_for_status()
            json_data = xml_to_json(response.text)
            json_conf.update(json_data)
    
    except requests.exceptions.RequestException as e:
        log_processor(plant, server, f"[ERROR] {camera_ip}: error al descargar configuración en '{get_conf}': {e}")
        return 790

    except xml.parsers.expat.ExpatError as e:
        log_processor(plant, server, f"[ERROR] {camera_ip}: respuesta XML inválida en '{get_conf}': {e}")
        return 790

    return json_conf


def xml_to_json(xml_data):
    xml_dict = xmltodict.parse(xml_data)
    return xml_dict