from file_processor import resolve_brand, InfoCam_url, mask_credentials, status_text, is_success_code


class TestResolveBrand:
    def test_axis(self):
        assert resolve_brand("http://user:pass@1.2.3.4/axis-cgi/jpg/image.cgi") == "AXIS"

    def test_hikvision(self):
        assert resolve_brand("http://user:pass@1.2.3.4/ISAPI/Streaming/channels/1/picture") == "HIKVISION"

    def test_vivotek(self):
        assert resolve_brand("rtsp://user:pass@1.2.3.4/media2/stream1") == "VIVOTEK"

    def test_dahua(self):
        assert resolve_brand("rtsp://user:pass@1.2.3.4/cam/realmonitor?channel=1") == "DAHUA"

    def test_desconocido(self):
        assert resolve_brand("rtsp://user:pass@1.2.3.4/algo/raro") == "DESCONOCIDO"

    def test_url_vacia_o_none(self):
        assert resolve_brand("") == "DESCONOCIDO"
        assert resolve_brand(None) == "DESCONOCIDO"


class TestInfoCamUrl:
    def test_con_usuario_y_password(self):
        info = InfoCam_url("rtsp://admin:Secreta1@192.168.1.50/axis-media/media.amp")
        assert info["user"] == "admin"
        assert info["password"] == "Secreta1"
        assert info["ip"] == "192.168.1.50"
        assert info["brand"] == "AXIS"
        assert info["channel"] == 1

    def test_con_canal_multisensor(self):
        info = InfoCam_url("rtsp://admin:pass@192.168.1.50/axis-media/media.amp?camera=3")
        assert info["channel"] == 3

    def test_sin_password(self):
        info = InfoCam_url("rtsp://solousuario@192.168.1.51/stream")
        assert info["user"] == "solousuario"
        assert info["password"] == ""
        assert info["ip"] == "192.168.1.51"

    def test_solo_ip(self):
        info = InfoCam_url("rtsp://192.168.1.52/cam/realmonitor")
        assert info["ip"] == "192.168.1.52"
        assert info["user"] == ""

    def test_url_vacia(self):
        info = InfoCam_url("")
        assert info["ip"] == ""
        assert info["brand"] == "DESCONOCIDO"


class TestMaskCredentials:
    def test_enmascara_usuario_y_password(self):
        url = "rtsp://admin:SuperSecreta123@192.168.1.50/axis-media/media.amp?camera=2"
        assert mask_credentials(url) == "rtsp://***:***@192.168.1.50/axis-media/media.amp?camera=2"

    def test_password_con_arroba(self):
        # Caso limite que se escapo la primera vez que se escribio la funcion.
        url = "http://usuario:P@ss@word@192.168.1.51/ISAPI/Streaming/channels/1/picture"
        assert mask_credentials(url) == "http://***:***@192.168.1.51/ISAPI/Streaming/channels/1/picture"

    def test_sin_credenciales_no_cambia(self):
        url = "rtsp://192.168.1.52/cam/realmonitor"
        assert mask_credentials(url) == url

    def test_url_vacia_o_none(self):
        assert mask_credentials("") == ""
        assert mask_credentials(None) is None


class TestStatusHelpers:
    def test_is_success_code_exito(self):
        assert is_success_code(100) is True   # Port 80 exitoso
        assert is_success_code(900) is True   # Server Found

    def test_is_success_code_error(self):
        assert is_success_code(111) is False  # Timed out
        assert is_success_code(620) is False  # Brand not found

    def test_is_success_code_desconocido(self):
        assert is_success_code(999999) is False

    def test_status_text_sin_prefijo(self):
        texto = status_text(100)
        assert "SUCCESS" not in texto
        assert "Port 80" in texto
        assert "[200]" in texto

    def test_status_text_codigo_desconocido(self):
        texto = status_text(999999)
        assert "999999" in texto
