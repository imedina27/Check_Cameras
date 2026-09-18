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

    def test_linea_con_igual_en_el_valor_se_pierde(self):
        # Caso limite documentado: Axis usa split("=") y exige exactamente 2
        # partes, asi que si el valor trae un "=" la linea se descarta entera.
        texto = "root.Algo.Valor=a=b\n"
        assert axis_dic_to_json(texto) == {}

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
