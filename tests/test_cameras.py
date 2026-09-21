import cameras
from cameras import Camera, CAMERA_HANDLERS


def _make_camera():
    return Camera(alias="TEST", brand="FAKE", cam_ip="1.2.3.4", cam_user="u", cam_pass="p",
                  serv_name="SRV", plant="PLANT", ia_port=1234, proxy_ip=None, proxy_port=None)


class TestCamConfigReintentos:
    def setup_method(self):
        self._original_handlers = dict(CAMERA_HANDLERS)

    def teardown_method(self):
        CAMERA_HANDLERS.clear()
        CAMERA_HANDLERS.update(self._original_handlers)

    def test_reintenta_y_se_recupera_tras_una_falla_transitoria(self, monkeypatch):
        # Caso real de producción: la primera petición falla por RemoteDisconnected
        # (bajo concurrencia), pero una segunda petición sobre la misma sesión
        # normalmente se recupera sola.
        monkeypatch.setattr(cameras.config, "MAX_CONFIG_RETRIES", 3)
        monkeypatch.setattr(cameras.config, "CONFIG_RETRY_DELAY", 0)
        monkeypatch.setattr(cameras, "save_json", lambda *a, **k: None)
        calls = {"n": 0}

        def flaky_config_func(*args, **kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                return 790
            return {"ok": True}

        CAMERA_HANDLERS["FAKE"] = (lambda *a, **k: b"img", flaky_config_func)

        resultado = _make_camera().Cam_Config()

        assert resultado == 700
        assert calls["n"] == 2

    def test_agota_reintentos_y_devuelve_el_ultimo_codigo_de_error(self, monkeypatch):
        monkeypatch.setattr(cameras.config, "MAX_CONFIG_RETRIES", 2)
        monkeypatch.setattr(cameras.config, "CONFIG_RETRY_DELAY", 0)
        calls = {"n": 0}

        def siempre_falla(*args, **kwargs):
            calls["n"] += 1
            return 790

        CAMERA_HANDLERS["FAKE"] = (lambda *a, **k: b"img", siempre_falla)

        resultado = _make_camera().Cam_Config()

        assert resultado == 790
        assert calls["n"] == 2

    def test_no_reintenta_si_la_primera_peticion_tiene_exito(self, monkeypatch):
        monkeypatch.setattr(cameras.config, "MAX_CONFIG_RETRIES", 3)
        monkeypatch.setattr(cameras.config, "CONFIG_RETRY_DELAY", 0)
        monkeypatch.setattr(cameras, "save_json", lambda *a, **k: None)
        calls = {"n": 0}

        def siempre_exitosa(*args, **kwargs):
            calls["n"] += 1
            return {"ok": True}

        CAMERA_HANDLERS["FAKE"] = (lambda *a, **k: b"img", siempre_exitosa)

        resultado = _make_camera().Cam_Config()

        assert resultado == 700
        assert calls["n"] == 1


class TestCamImageReintentos:
    # Antes Cam_Image() no tenia ningun reintento — confirmado en produccion
    # que "Imagen camara: Timed out" aumenta bajo concurrencia, mismo tipo de
    # congestion transitoria que ya se arreglo en Cam_Config().
    def setup_method(self):
        self._original_handlers = dict(CAMERA_HANDLERS)

    def teardown_method(self):
        CAMERA_HANDLERS.clear()
        CAMERA_HANDLERS.update(self._original_handlers)

    def test_reintenta_y_se_recupera_tras_una_falla_transitoria(self, monkeypatch):
        monkeypatch.setattr(cameras.config, "MAX_IMAGE_RETRIES", 3)
        monkeypatch.setattr(cameras.config, "IMAGE_RETRY_DELAY", 0)
        monkeypatch.setattr(cameras, "save_img", lambda *a, **k: 601)
        calls = {"n": 0}

        def flaky_image_func(*args, **kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                return 611
            return b"img-bytes"

        CAMERA_HANDLERS["FAKE"] = (flaky_image_func, lambda *a, **k: {"ok": True})

        resultado = _make_camera().Cam_Image()

        assert resultado == 601
        assert calls["n"] == 2

    def test_agota_reintentos_y_devuelve_el_ultimo_codigo_de_error(self, monkeypatch):
        monkeypatch.setattr(cameras.config, "MAX_IMAGE_RETRIES", 2)
        monkeypatch.setattr(cameras.config, "IMAGE_RETRY_DELAY", 0)
        calls = {"n": 0}

        def siempre_falla(*args, **kwargs):
            calls["n"] += 1
            return 611

        CAMERA_HANDLERS["FAKE"] = (siempre_falla, lambda *a, **k: {"ok": True})

        resultado = _make_camera().Cam_Image()

        assert resultado == 611
        assert calls["n"] == 2

    def test_no_reintenta_si_la_primera_peticion_tiene_exito(self, monkeypatch):
        monkeypatch.setattr(cameras.config, "MAX_IMAGE_RETRIES", 3)
        monkeypatch.setattr(cameras.config, "IMAGE_RETRY_DELAY", 0)
        monkeypatch.setattr(cameras, "save_img", lambda *a, **k: 601)
        calls = {"n": 0}

        def siempre_exitosa(*args, **kwargs):
            calls["n"] += 1
            return b"img-bytes"

        CAMERA_HANDLERS["FAKE"] = (siempre_exitosa, lambda *a, **k: {"ok": True})

        resultado = _make_camera().Cam_Image()

        assert resultado == 601
        assert calls["n"] == 1


class TestCamAIImageReintentos:
    def test_espera_entre_intentos_cuando_falla(self, monkeypatch):
        # Antes los reintentos de Cam_AI_Image() se hacian de inmediato, sin
        # ninguna espera entre ellos — no le daban tiempo a la congestion del
        # proxy a despejarse. Ahora debe esperar IMAGE_RETRY_DELAY entre intentos.
        monkeypatch.setattr(cameras.config, "MAX_IMAGE_RETRIES", 3)
        monkeypatch.setattr(cameras.config, "IMAGE_RETRY_DELAY", 0)
        esperas = []
        monkeypatch.setattr(cameras.time, "sleep", lambda s: esperas.append(s))

        import requests

        class _FakeSession:
            def get(self, *a, **k):
                raise requests.exceptions.Timeout()

        cam = _make_camera()
        cam.session = _FakeSession()

        resultado = cam.Cam_AI_Image()

        assert resultado == 611
        assert len(esperas) == 2  # una espera entre cada uno de los 3 intentos, no despues del ultimo
