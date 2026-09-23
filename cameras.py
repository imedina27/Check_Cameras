from conf.cameras.axis import AxisCamConf, AxisCamImage
from conf.cameras.hikvision import HikvCamConf, HikvCamImage
from conf.cameras.vivotek import VivoCamImage, VivoCamConf
from conf.cameras.dahua import DahuaCamImage, DahuaCamConf
from file_processor import save_img, save_json
import config
import requests
import time


# Registro de manejadores por marca de cámara: brand -> (func_imagen, func_config).
# Para agregar una marca nueva:
#   1. Crear conf/cameras/<marca>.py con <Marca>CamImage y <Marca>CamConf,
#      misma firma que las existentes: (session, camera_ip, username, password,
#      proxy_ip, proxy_port, channel=1).
#   2. Agregar la entrada aquí.
#   3. Agregar el patrón de detección en resolve_brand() (file_processor.py) —
#      si no, esa marca nunca se identifica a partir de la videoURL y nunca
#      llega a usar el manejador de aquí.
CAMERA_HANDLERS = {
    "AXIS":      (AxisCamImage, AxisCamConf),
    "HIKVISION": (HikvCamImage, HikvCamConf),
    "VIVOTEK":   (VivoCamImage, VivoCamConf),
    "DAHUA":     (DahuaCamImage, DahuaCamConf),
}


class Camera:
    def __init__(self, alias, brand, cam_ip, cam_user, cam_pass, serv_name, plant, ia_port, proxy_ip, proxy_port, channel=1, result_path=None):
        self.alias = alias
        self.brand = brand
        self.cam_ip = cam_ip
        self.cam_user = cam_user
        self.cam_pass = cam_pass
        self.plant = plant
        self.serv_name = serv_name
        self.ia_port = ia_port
        self.proxy_port = proxy_port
        self.proxy_ip = proxy_ip
        self.channel = channel
        self.result_path = result_path
        # Session compartida entre todas las peticiones de esta cámara:
        # reutiliza la conexión TCP en vez de abrir una nueva por cada request.
        self.session = requests.Session()

    def Cam_Up(self):                       #---------- PROBADO ----------#
        if self.proxy_ip and self.proxy_port:
            proxy = {'http': f'http://{self.proxy_ip}:{self.proxy_port}'}
        else:
            proxy = {}
        
        # Usar configuración de reintentos
        max_retries = config.MAX_CAMERA_RETRIES
        current_attempt = 0
        
        while current_attempt < max_retries:
            try:
                # Usar timeout configurable
                response = self.session.head(f'http://{self.cam_ip}',
                                       proxies=proxy,
                                       timeout=config.CAMERA_PORT_TIMEOUT)
                response.raise_for_status()
                return 100
            except requests.exceptions.HTTPError as e:
                # Incrementar el contador de intentos
                current_attempt += 1
                if current_attempt >= max_retries:
                    return e.response.status_code
                # Usar delay configurable
                time.sleep(config.PORT80_DELAY)
            except requests.exceptions.Timeout:
                current_attempt += 1
                if current_attempt >= max_retries:
                    return 111
                time.sleep(config.PORT80_DELAY)
            except requests.exceptions.RequestException as e:
                current_attempt += 1
                if current_attempt >= max_retries:
                    # Asegurar un valor de retorno numérico consistente
                    if hasattr(e, 'errno') and isinstance(e.errno, int):
                        return e.errno
                    else:
                        # Código genérico para errores de conexión
                        return 190
                time.sleep(config.PORT80_DELAY)


    def Cam_AI_Image(self):                 #---------- PROBADO ----------#
        if self.proxy_ip:
            img_ai_url = f"http://{self.proxy_ip}:{self.ia_port}/oneshot/{self.alias}"
        else:
            img_ai_url = f"http://localhost:{self.ia_port}/oneshot/{self.alias}"
        cam_res = 690
        max_attempts = config.MAX_IMAGE_RETRIES

        for attempt in range(max_attempts):
            try:
                response = self.session.get(img_ai_url, timeout=config.IMAGE_TIMEOUT)
                status_code = response.status_code

                if status_code == 200:
                    cam_img = response.content
                    cam_res = save_img(cam_img, self.plant, self.serv_name, self.alias, True, result_path=self.result_path)
                    return cam_res
                else:
                    cam_res = 503

            except requests.exceptions.Timeout:
                cam_res = 611
            except requests.exceptions.RequestException as e:
                cam_res = 503
            # Espera antes de reintentar (salvo en el último intento): antes
            # los reintentos se hacían de inmediato, uno tras otro, sin dar
            # tiempo a que se despeje una congestión transitoria del proxy.
            if attempt < max_attempts - 1:
                time.sleep(config.IMAGE_RETRY_DELAY)
        return cam_res


    def Cam_Image(self):                    #---------- PROBADO ----------#
        handlers = CAMERA_HANDLERS.get(self.brand)
        if handlers is None:
            return 620
        image_func, _ = handlers

        # Reintentar ante cualquier falla, mismo patrón que Cam_Config():
        # antes esta llamada no tenía ningún reintento — confirmado en
        # producción que las fallas de "Imagen cámara: Timed out" aumentan
        # bajo concurrencia (varias cámaras fallando casi al mismo segundo),
        # el mismo tipo de congestión transitoria que ya vimos con Cam_Config.
        max_retries = config.MAX_IMAGE_RETRIES
        cam_img = 690
        for attempt in range(max_retries):
            cam_img = image_func(self.session, self.cam_ip, self.cam_user, self.cam_pass,
                                 self.proxy_ip, self.proxy_port, self.channel, self.plant, self.serv_name)
            if not isinstance(cam_img, int):
                break
            if attempt < max_retries - 1:
                time.sleep(config.IMAGE_RETRY_DELAY)

        if isinstance(cam_img, int):
            return cam_img
        else:
            cam_img = save_img(cam_img, self.plant, self.serv_name, self.alias, False, result_path=self.result_path)
            if cam_img == 600:
                cam_img = 601
            return cam_img
        
        
    def Cam_Config(self):                   #---------- PROBADO ----------#
        handlers = CAMERA_HANDLERS.get(self.brand)
        if handlers is None:
            return 720
        _, config_func = handlers

        # Reintentar toda la descarga de configuración ante cualquier falla:
        # a diferencia de Cam_Up/Cam_AI_Image, esta llamada no tenía reintentos,
        # y es puramente lectura (GET), así que reintentar es seguro. Mitiga
        # fallas transitorias de conexión bajo concurrencia (confirmado en
        # producción: RemoteDisconnected en Hikvision, mucho más frecuente al
        # revisar cámaras en paralelo que de forma secuencial).
        max_retries = config.MAX_CONFIG_RETRIES
        cam_conf = 790
        for attempt in range(max_retries):
            cam_conf = config_func(self.session, self.cam_ip, self.cam_user, self.cam_pass,
                                   self.proxy_ip, self.proxy_port, self.channel, self.plant, self.serv_name)
            if not isinstance(cam_conf, int):
                break
            if attempt < max_retries - 1:
                time.sleep(config.CONFIG_RETRY_DELAY)

        if isinstance(cam_conf, int):
                return cam_conf
        else:
            save_json(cam_conf, self.plant, self.serv_name, self.alias, result_path=self.result_path)
            status = 700
            return status