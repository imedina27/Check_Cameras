import requests
import xmltodict
import urllib.parse
import config


def HikvCamImage(camera_ip, username, password, proxy_ip, proxy_port):
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
    

def HikvCamConf(camera_ip, username, password, proxy_ip, proxy_port):
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
    ]

    json_conf = {}

    try:
        for get_conf in get_confs:
            grl_url = f'http://{camera_ip}/ISAPI/{get_conf}'
            
            # Usar timeout configurable para cada petición de configuración
            response = requests.get(grl_url, headers=headers, auth=auth,  
                                  proxies=proxies, timeout=config.CONF_TIMEOUT)
            response.raise_for_status()
            json_data = xml_to_json(response.text)
            json_conf.update(json_data)
    
    except requests.exceptions.RequestException as e:
        return 790
    
    return json_conf


def xml_to_json(xml_data):
    xml_dict = xmltodict.parse(xml_data)
    return xml_dict