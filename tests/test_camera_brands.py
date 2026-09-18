from conf.cameras.axis import dic_to_json as axis_dic_to_json
from conf.cameras.dahua import dic_to_json as dahua_dic_to_json
from conf.cameras.vivotek import txt_to_json as vivotek_txt_to_json


class TestAxisDicToJson:
    def test_estructura_anidada_basica(self):
        texto = "root.Network.eth0.IPAddress=192.168.1.50\nroot.Brand.ProdNbr=M3057\n"
        assert axis_dic_to_json(texto) == {
            "Network": {"eth0": {"IPAddress": "192.168.1.50"}},
            "Brand": {"ProdNbr": "M3057"},
        }

    def test_linea_con_igual_en_el_valor_si_se_conserva(self):
        # Corregido: Axis usaba split("=") y perdia la linea completa si el
        # valor traia un "=" (confirmado con datos reales: pasaba en las
        # posiciones de preset de PTZ y perfiles de multicast). Ahora usa
        # partition("="), igual que Dahua, y si conserva el valor completo.
        texto = "root.Algo.Valor=a=b\n"
        assert axis_dic_to_json(texto) == {"Algo": {"Valor": "a=b"}}

    def test_valor_con_varios_signos_igual_ptz_preset(self):
        # Caso real encontrado en produccion (posicion de preset de PTZ)
        texto = "root.PTZ.Preset.P0.Position.P1.Data=pan=0.000000:tilt=0.000000:zoom=1.000000\n"
        resultado = axis_dic_to_json(texto)
        assert resultado["PTZ"]["Preset"]["P0"]["Position"]["P1"]["Data"] == "pan=0.000000:tilt=0.000000:zoom=1.000000"

    def test_texto_vacio(self):
        assert axis_dic_to_json("") == {}


class TestDahuaDicToJson:
    def test_estructura_anidada_basica(self):
        texto = "table.Network.eth0.IPAddress=192.168.1.50\ntable.Brand.ProdNbr=M3057\n"
        assert dahua_dic_to_json(texto) == {
            "Network": {"eth0": {"IPAddress": "192.168.1.50"}},
            "Brand": {"ProdNbr": "M3057"},
        }

    def test_linea_con_igual_en_el_valor_si_se_conserva(self):
        # A diferencia de Axis/Vivotek, Dahua usa partition("=") (solo el
        # primer "=") y SI conserva el resto del valor.
        texto = "table.Algo.Valor=a=b\n"
        assert dahua_dic_to_json(texto) == {"Algo": {"Valor": "a=b"}}

    def test_texto_vacio(self):
        assert dahua_dic_to_json("") == {}


class TestVivotekTxtToJson:
    def test_estructura_anidada_con_guion_bajo(self):
        texto = "network_interface_ip='192.168.1.50'\n"
        assert vivotek_txt_to_json(texto) == {"network": {"interface": {"ip": "192.168.1.50"}}}

    def test_quita_comillas_simples_del_valor(self):
        texto = "system_hostname='CAM01'\n"
        resultado = vivotek_txt_to_json(texto)
        assert resultado["system"]["hostname"] == "CAM01"

    def test_texto_vacio(self):
        assert vivotek_txt_to_json("") == {}
