import requests
import urllib.parse
import config


def AxisCamImage(session, camera_ip, username, password, proxy_ip, proxy_port, channel=1):
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
        return 611

    except requests.exceptions.ConnectionError:
        return 620

    except requests.exceptions.RequestException:
        return 690


def AxisCamConf(session, camera_ip, username, password, proxy_ip, proxy_port, channel=1):
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
        return 701
    
    except requests.exceptions.RequestException as e:
        return 790
    
    return json_conf


def dic_to_json(text):
    # Convierte un diccionario Plano separado por puntos en un json
    
    config_dict = {}

    for line in text.split('\n'):
        line = line.strip()
        key_value = line.split("=")
        if len(key_value) == 2:
            key = key_value[0].strip()
            value = key_value[1].strip()
            key_parts = key.split(".")[1:]  # Excluir "root"
            current_dict = config_dict

            for part in key_parts[:-1]:
                if part not in current_dict:
                    current_dict[part] = {}
                current_dict = current_dict[part]

            current_dict[key_parts[-1]] = value
    
    return config_dict