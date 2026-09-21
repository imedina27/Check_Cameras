from file_processor import resolve_brand, InfoCam_url, mask_credentials, status_text, is_success_code, _status_parts, write_summary
import file_processor
import config


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

    def test_status_parts_separa_descripcion_y_codigo_en_exito(self):
        descripcion, codigo = _status_parts(100)
        assert descripcion == "Port 80"
        assert codigo == "200"

    def test_status_parts_separa_descripcion_y_codigo_en_error(self):
        # El proceso y el codigo interno estan desacoplados: la descripcion
        # no lleva el nombre del proceso, para poder anteponer un campo
        # PROCESO explicito en el log sin duplicar informacion.
        descripcion, codigo = _status_parts(111)
        assert descripcion == "Timed out"
        assert codigo == "111"

    def test_status_parts_codigo_no_registrado_en_el_catalogo(self):
        descripcion, codigo = _status_parts(701)
        assert descripcion == "Unknown status code"
        assert codigo == "701"


def _cam(complete):
    return {"alias": "A1", "ip": "1.2.3.4", "failures": [] if complete else ["Puerto 80: Timed out [111]"], "complete": complete}


class TestWriteSummaryDetallePorServidor:
    # DETALLE POR SERVIDOR debe listar TODOS los servidores, uno por linea,
    # con estado explicito (OK/CON FALLAS/SIN CONEXION) — a diferencia del
    # resto del resumen, que solo lista por excepcion y no distingue "todo
    # bien" de "nunca se reviso" (hallazgo real del usuario).
    def _run(self, tmp_path, monkeypatch, server_results):
        monkeypatch.setattr(config, "RESULT_PATH", str(tmp_path))
        file_processor._dirs_ensured.clear()
        write_summary(server_results)
        [resumen] = list(tmp_path.rglob("resumen_*.log"))
        return resumen.read_text(encoding="utf-8")

    def test_servidor_ok_sin_ninguna_falla(self, tmp_path, monkeypatch):
        server_results = [
            {"serv_name": "SRV1", "plant": "PLANTA1", "problem": None, "cameras": [_cam(True), _cam(True)]},
        ]
        texto = self._run(tmp_path, monkeypatch, server_results)
        assert "[OK]   PLANTA1   SRV1   2/2 cámaras completas" in texto

    def test_servidor_con_al_menos_una_falla(self, tmp_path, monkeypatch):
        server_results = [
            {"serv_name": "SRV1", "plant": "PLANTA1", "problem": None, "cameras": [_cam(True), _cam(False)]},
        ]
        texto = self._run(tmp_path, monkeypatch, server_results)
        assert "[CON FALLAS]   PLANTA1   SRV1   1/2 cámaras completas" in texto

    def test_servidor_sin_conexion_no_desaparece(self, tmp_path, monkeypatch):
        server_results = [
            {"serv_name": "SRV1", "plant": "PLANTA1", "problem": "Sin IP disponible (zerotier/local/cámaras)", "cameras": []},
        ]
        texto = self._run(tmp_path, monkeypatch, server_results)
        assert "[SIN CONEXIÓN]   PLANTA1   SRV1   Sin IP disponible (zerotier/local/cámaras)" in texto

    def test_servidor_sin_yaml_usa_su_propia_etiqueta(self, tmp_path, monkeypatch):
        # Distinto de [SIN CONEXIÓN]: el servidor sí respondió, pero no se
        # pudo leer el listado de cámaras (bug real: antes esto se perdía
        # y el servidor aparecía como [OK] 0/0). El detalle del error ya
        # está en el log de esa planta, así que aquí solo se muestra "-/-"
        # (no un "0/0": nunca se supo cuántas cámaras hay realmente).
        server_results = [
            {"serv_name": "SRV1", "plant": "PLANTA1", "problem": "No se pudo leer el YAML de cámaras (puerto 8045: YAML Connection error [410])",
             "problem_type": "sin_yaml", "cameras": []},
        ]
        texto = self._run(tmp_path, monkeypatch, server_results)
        assert "[SIN YAML]   PLANTA1   SRV1   -/- cámaras completas" in texto
        assert "[SIN CONEXIÓN]" not in texto
        assert "[OK]" not in texto
        assert "YAML Connection error" not in texto

    def test_columnas_no_se_pegan_con_nombres_largos(self, tmp_path, monkeypatch):
        # Bug real: con ancho fijo, "API-MANZANILLO" (14 caracteres) se
        # pegaba directo con el nombre del servidor siguiente, sin espacio.
        server_results = [
            {"serv_name": "APIMAN-FASE1", "plant": "API-MANZANILLO", "problem": None, "cameras": [_cam(True)]},
        ]
        texto = self._run(tmp_path, monkeypatch, server_results)
        assert "API-MANZANILLOAPIMAN-FASE1" not in texto
        assert "API-MANZANILLO   APIMAN-FASE1" in texto

    def test_todos_los_servidores_aparecen_aunque_esten_perfectos(self, tmp_path, monkeypatch):
        server_results = [
            {"serv_name": "SRV1", "plant": "PLANTA1", "problem": None, "cameras": [_cam(True)]},
            {"serv_name": "SRV2", "plant": "PLANTA2", "problem": None, "cameras": [_cam(True)]},
        ]
        texto = self._run(tmp_path, monkeypatch, server_results)
        assert texto.count("[OK]") == 2

    def test_respeta_la_estrategia_de_orden_configurada(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "LOG_SORT_STRATEGY", "numeric_suffix")
        server_results = [
            {"serv_name": "QLYMSPROD11", "plant": "ATLANTICO", "problem": None, "cameras": [_cam(True)]},
            {"serv_name": "QLYMSPROD02", "plant": "ZACATECAS", "problem": None, "cameras": [_cam(True)]},
        ]
        texto = self._run(tmp_path, monkeypatch, server_results)
        seccion = texto.split("DETALLE POR SERVIDOR")[1].split("=" * 42)[0]
        assert seccion.index("QLYMSPROD02") < seccion.index("QLYMSPROD11")


def _fail_cam(alias, ip, *fallas):
    return {"alias": alias, "ip": ip, "failures": list(fallas), "complete": False}


class TestWriteSummaryDetallePorPlanta:
    def _run(self, tmp_path, monkeypatch, server_results, strategy="alphabetical"):
        monkeypatch.setattr(config, "RESULT_PATH", str(tmp_path))
        monkeypatch.setattr(config, "LOG_SORT_STRATEGY", strategy)
        file_processor._dirs_ensured.clear()
        write_summary(server_results)
        [resumen] = list(tmp_path.rglob("resumen_*.log"))
        return resumen.read_text(encoding="utf-8")

    def test_ordena_camaras_por_tipo_de_falla_y_luego_alfabetico(self, tmp_path, monkeypatch):
        # Puerto 80 antes que Imagen IA aunque el alias sea alfabeticamente posterior
        server_results = [{
            "serv_name": "SRV1", "plant": "PLANTA1", "problem": None,
            "cameras": [
                _fail_cam("Z1", "1.1.1.1", "Imagen IA: Timed out [601]"),
                _fail_cam("A1", "1.1.1.2", "Puerto 80: Timed out [111]"),
                _fail_cam("B1", "1.1.1.3", "Puerto 80: Timed out [111]"),
            ],
        }]
        texto = self._run(tmp_path, monkeypatch, server_results)
        detalle = texto.split("DETALLE POR PLANTA")[1]
        assert detalle.index("A1") < detalle.index("B1") < detalle.index("Z1")

    def test_camara_con_varias_fallas_usa_la_mas_temprana_para_ordenar(self, tmp_path, monkeypatch):
        server_results = [{
            "serv_name": "SRV1", "plant": "PLANTA1", "problem": None,
            "cameras": [
                _fail_cam("Z1", "1.1.1.1", "Configuración: Unknow error [790]"),
                _fail_cam("A1", "1.1.1.2", "Imagen IA: Timed out [601]", "Configuración: Unknow error [790]"),
            ],
        }]
        texto = self._run(tmp_path, monkeypatch, server_results)
        detalle = texto.split("DETALLE POR PLANTA")[1]
        # A1 tiene Imagen IA (prioridad mas alta) entre sus fallas, va primero
        assert detalle.index("A1") < detalle.index("Z1")

    def test_separador_entre_servidores_de_la_misma_planta(self, tmp_path, monkeypatch):
        server_results = [
            {"serv_name": "SRV1", "plant": "PLANTA1", "problem": None,
             "cameras": [_fail_cam("A1", "1.1.1.1", "Puerto 80: Timed out [111]")]},
            {"serv_name": "SRV2", "plant": "PLANTA1", "problem": None,
             "cameras": [_fail_cam("A2", "1.1.1.2", "Puerto 80: Timed out [111]")]},
        ]
        texto = self._run(tmp_path, monkeypatch, server_results)
        detalle = texto.split("DETALLE POR PLANTA")[1]
        assert detalle.count("PLANTA1:") == 1
        assert "=" * 60 in detalle

    def test_plantas_ordenadas_por_la_estrategia_configurada(self, tmp_path, monkeypatch):
        server_results = [
            {"serv_name": "QLYMSPROD11", "plant": "ATLANTICO", "problem": None,
             "cameras": [_fail_cam("A1", "1.1.1.1", "Puerto 80: Timed out [111]")]},
            {"serv_name": "QLYMSPROD02", "plant": "ZACATECAS", "problem": None,
             "cameras": [_fail_cam("A2", "1.1.1.2", "Puerto 80: Timed out [111]")]},
        ]
        texto = self._run(tmp_path, monkeypatch, server_results, strategy="numeric_suffix")
        detalle = texto.split("DETALLE POR PLANTA")[1]
        assert detalle.index("ZACATECAS:") < detalle.index("ATLANTICO:")
