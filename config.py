import os
from dotenv import load_dotenv

load_dotenv()

# ============================================
# CONFIGURACIÓN DE ENTORNO (desde .env)
# ============================================

# LocalHost
LOCAL_HOST  = os.getenv('LOCAL_HOST', 'NOQUANTUM')

# Directorios
RESULT_PATH = os.getenv('RESULT_PATH', './results')

# Archivo de plantas a usar (varía según el entorno: Windows local vs Ubuntu Server)
PLANTS_FILE = os.getenv('PLANTS_FILE', 'plants.yaml')

# Puertos locales para tuneles
PX_LOC_PORT = int(os.getenv('PX_LOC_PORT', 39533))
IA_LOC_PORT = int(os.getenv('IA_LOC_PORT', 9045))
PX_PID_FILE = os.getenv('PX_PID_FILE', '/tmp/ssh_px_tunnel.pid')
IA_PID_FILE = os.getenv('IA_PID_FILE', '/tmp/ssh_ia_tunnel.pid')

# Ping
MAX_PING_ATTEMPTS = int(os.getenv('MAX_PING_ATTEMPTS', 3))
PING_TIMEOUT = int(os.getenv('PING_TIMEOUT', 3))
RETRY_DELAY = int(os.getenv('RETRY_DELAY', 1))

# Image
MAX_IMAGE_RETRIES = int(os.getenv('MAX_AI_RETRIES', 3))
IMAGE_TIMEOUT = int(os.getenv('AI_IMAGE_TIMEOUT', 3))

# Configuartion
CONF_TIMEOUT = int(os.getenv('CONF_TIMEOUT', 3))

# Timeouts para YAML
YAML_TIMEOUT = int(os.getenv('YAML_TIMEOUT', 3))

# Puerto 80 en Camaras
MAX_CAMERA_RETRIES = int(os.getenv('MAX_CAMERA_RETRIES', 3))
CAMERA_PORT_TIMEOUT = int(os.getenv('CAMERA_PORT_TIMEOUT', 3))
PORT80_DELAY = int(os.getenv('PORT80_DELAY', 1))

# RETRIES FOR CLOSE TUNNELS
MAX_RETRIES = int(os.getenv('MAX_RETRIES', 2))

# Umbral de tiempo (segundos) para el proceso completo de una cámara
# (Cam_Up + Cam_AI_Image + Cam_Image + Cam_Config). Solo es visibilidad en el
# log (verde/amarillo), no cancela ni omite nada.
CAM_TIME_THRESHOLD = int(os.getenv('CAM_TIME_THRESHOLD', 15))


# ============================================
# CONSTANTES DE APLICACIÓN
# ============================================
STATUS_MESSAGES = {
    # Port 80
    100: "[SUCCESS] Port 80                 [200]",
    111: "[ERROR]   Timed out               [111]",
    190: "[ERROR]   Connection error        [199]",

    # CONFIG_YAML
    400: "[SUCCESS] YAML Read successful    [200]",
    404: "[ERROR]   Not Found               [404]",
    410: "[ERROR]   YAML Connection error   [410]",
    411: "[ERROR]   YAML Read timeout       [411]",
    412: "[ERROR]   Invalid YAML format     [412]",
    413: "[ERROR]   HTTP error reading YAML [413]",
    414: "[ERROR]   Empty YAML URL          [414]",
    415: "[ERROR]   Unexpected error         [415]",
    
    # HTTP Errores
    503: "[ERROR]   Service Unavailable     [503]",
    
    # Images
    600: "[SUCCESS] IA Image Save           [200]",
    601: "[SUCCESS] CAM Image Save          [200]",
    611: "[ERROR]   Timed out               [601]",
    613: "[ERROR]   Connection error        [613]",
    620: "[ERROR]   Brand not found         [620]",
    630: "[ERROR]   Service Unavailable     [630]",
    640: "[ERROR]   URL error               [630]",
    690: "[ERROR]   Unknow error            [690]",

    # Configuarcion de camara
    700: "[SUCCESS] Configuartion Save      [200]",
    711: "[ERROR]   Timed out               [701]",
    713: "[ERROR]   Connection error        [713]",
    720: "[ERROR]   Brand not found         [720]",
    730: "[ERROR]   Service Unavailable     [730]",
    790: "[ERROR]   Unknow error            [790]",

    # PING
    800: "[SUCCESS] Ping                    [200]",
    810: "[ERROR]   Unreachable             [810]",
    811: "[ERROR]   Timed out               [811]",
    812: "[ERROR]   Unknown host            [812]",
    813: "[ERROR]   Error general           [813]",
    814: "[ERROR]   Not configured          [814]",
    
    # Archivo plant.yaml
    900: "[SUCCESS] Server Found            [200]",
    901: "[ERROR]   Server not found        [901]",
    902: "[ERROR]   Server Deactivated      [902]",
    903: "[ERROR]   YAML not found          [903]",
    904: "[ERROR]   Parsing YAML            [904]",
    905: "[ERROR]   General/Unespected      [905]"
}