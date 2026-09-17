import requests
import urllib.parse
import config


def VivoCamImage(camera_ip, username, password, proxy_ip, proxy_port):
    password = urllib.parse.unquote(password)

    img_urls = [
        f"http://{camera_ip}/cgi-bin/viewer/video.jpg",
        f"http://{camera_ip}/cgi-bin/viewer/video.jpg?channel=0",
        f"http://{camera_ip}/video.jpg",
        f"http://{camera_ip}/cgi-bin/jpeg.cgi",
        f"http://{camera_ip}/cgi-bin/viewer/snapshot.cgi",
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

    auth = requests.auth.HTTPBasicAuth(username, password)

    try:
        for img_url in img_urls:
            try:
                response = requests.get(img_url, headers=headers, auth=auth,
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


def VivoCamConf(camera_ip, username, password, proxy_ip, proxy_port):
    # Decodificar la contraseña si contiene caracteres codificados como %40
    password = urllib.parse.unquote(password)
        
    grl_url = f"http://{camera_ip}/cgi-bin/admin/getparam.cgi?network&videoin&system"

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
        response = requests.get(grl_url, headers=headers, auth=auth, 
                              proxies=proxies, timeout=config.IMAGE_TIMEOUT)
        response.raise_for_status()
        json_conf = txt_to_json(response.text)
    
    except requests.exceptions.Timeout:
        return 701
    
    except requests.exceptions.RequestException as e:
        return 790
    
    return json_conf


def txt_to_json(text):
    config_dict = {}

    for line in text.split('\n'):
        line = line.strip()
        key_value = line.split("=")
        if len(key_value) == 2:
            key = key_value[0].strip()
            value = key_value[1].strip().strip("'")
            key_parts = key.split("_")  # Vivotek usa _ en lugar de .
            current_dict = config_dict

            for part in key_parts[:-1]:
                if part not in current_dict:
                    current_dict[part] = {}
                current_dict = current_dict[part]

            current_dict[key_parts[-1]] = value

    return config_dict