import requests
import urllib.parse
import config
from file_processor import log_processor


def DahuaCamImage(session, camera_ip, username, password, proxy_ip, proxy_port, channel=1, plant=None, server=None):
    password = urllib.parse.unquote(password)

    img_urls = [
        f"http://{camera_ip}/cgi-bin/snapshot.cgi?channel={channel}",
        f"http://{camera_ip}/cgi-bin/snapshot.cgi?chn={channel}",
        f"http://{camera_ip}/cgi-bin/snapshot.cgi",
    ]

    headers = {
        "Accept": "image/jpeg"
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


def DahuaCamConf(session, camera_ip, username, password, proxy_ip, proxy_port, channel=1, plant=None, server=None):
    password = urllib.parse.unquote(password)

    headers = {
        "Accept": "text/plain"
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
        f"/cgi-bin/magicBox.cgi?action=getDeviceType",
        f"/cgi-bin/magicBox.cgi?action=getSerialNo",
        f"/cgi-bin/magicBox.cgi?action=getSoftwareVersion",
        f"/cgi-bin/configManager.cgi?action=getConfig&name=Network",
        f"/cgi-bin/configManager.cgi?action=getConfig&name=VideoColor[{channel-1}]",
        f"/cgi-bin/configManager.cgi?action=getConfig&name=Encode[{channel-1}]",
    ]

    json_conf = {}

    try:
        for get_conf in get_confs:
            url = f"http://{camera_ip}{get_conf}"
            response = session.get(url, headers=headers, auth=auth,
                                    proxies=proxies, timeout=config.CONF_TIMEOUT)
            response.raise_for_status()
            parsed = dic_to_json(response.text)
            json_conf.update(parsed)

    except requests.exceptions.RequestException as e:
        log_processor(plant, server, f"[ERROR] {camera_ip}: error al descargar configuración en '{get_conf}': {e}")
        return 790

    return json_conf


def dic_to_json(text, prefix_levels=1):
    """
    Convierte respuesta Dahua key=value a dict anidado.
    prefix_levels: cuántos niveles iniciales omitir (1 = omite 'table')
    """
    config_dict = {}

    for line in text.strip().splitlines():
        line = line.strip()
        if "=" not in line:
            continue

        key, _, value = line.partition("=")
        key_parts = key.strip().split(".")[prefix_levels:]  # Omitir 'table'

        if not key_parts:
            continue

        current_dict = config_dict
        for part in key_parts[:-1]:
            if part not in current_dict:
                current_dict[part] = {}
            current_dict = current_dict[part]

        current_dict[key_parts[-1]] = value.strip()

    return config_dict