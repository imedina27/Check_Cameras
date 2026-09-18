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

    # Antes: 6 peticiones (tipo, serie, versión, y Network/VideoColor/Encode
    # por separado, cubriendo solo 3 secciones reales de configuración).
    # Verificado en vivo contra una DH-IPC-HDBW3549R1: "getSystemInfo" agrupa
    # tipo+serie+versión de hardware en 1 sola llamada, y
    # "getConfig&name=All" trae TODA la configuración (577 secciones reales,
    # ~985 KB) en 1 sola llamada, en vez de pedir Network/VideoColor/Encode
    # de a uno. Total: 3 peticiones en vez de 6, con muchísima más cobertura.
    # "name=All" NO incluye cuentas de usuario/contraseñas (verificado: cero
    # líneas "Account" en la respuesta) — Dahua parece excluirlas a propósito.
    # channel ya no se usa aquí (antes filtraba VideoColor/Encode a un solo
    # canal; "All" ya trae todos los canales) — se deja en la firma por
    # consistencia con el registro de marcas (CAMERA_HANDLERS, Fase 3).
    solicitudes = [
        ("/cgi-bin/magicBox.cgi?action=getSystemInfo", 0),
        ("/cgi-bin/magicBox.cgi?action=getSoftwareVersion", 0),
        ("/cgi-bin/configManager.cgi?action=getConfig&name=All", 2),
    ]

    json_conf = {}

    try:
        for get_conf, prefix_levels in solicitudes:
            url = f"http://{camera_ip}{get_conf}"
            response = session.get(url, headers=headers, auth=auth,
                                    proxies=proxies, timeout=config.CONF_TIMEOUT)
            response.raise_for_status()
            parsed = dic_to_json(response.text, prefix_levels=prefix_levels)
            json_conf.update(parsed)

    except requests.exceptions.RequestException as e:
        log_processor(plant, server, f"[ERROR] {camera_ip}: error al descargar configuración en '{get_conf}': {e}")
        return 790

    return json_conf


def dic_to_json(text, prefix_levels=1):
    """
    Convierte respuesta Dahua key=value a dict anidado.
    prefix_levels: cuántos niveles iniciales omitir (1 = omite 'table',
    2 = omite 'table' y 'All' cuando se pide name=All).

    LIMITACIÓN CONOCIDA (documentada, no corregida — caso extremadamente
    raro): si una misma ruta de clave aparece a la vez como valor final Y
    como padre de otra clave más profunda, la primera se pierde. Ejemplo
    real visto en producción (respuesta de "name=All" de una DH-IPC-HDBW3549R1,
    1 caso en 15,846 líneas):
        table.All.P2PLimit.Video=<valor>
        table.All.P2PLimit.Video.resolution=<valor>
    Al construir el diccionario anidado, la segunda línea convierte
    "P2PLimit.Video" en un dict (para meter "resolution" adentro), y el
    valor plano de la primera línea se sobreescribe. No hay forma de
    representar ambas cosas en un dict normal de Python sin cambiar la
    estructura de salida (ej. guardar el valor bajo una clave especial como
    "_value"), así que se dejó documentado en vez de complicar el formato.
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