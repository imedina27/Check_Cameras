from sort_strategies import get_sort_key


class TestNumericSuffixStrategy:
    def test_ordena_por_numero_sin_importar_el_prefijo(self):
        key = get_sort_key("numeric_suffix")
        nombres = ["QBYMSPROD07", "QLYMSPROD02", "QLYMSPROD11", "QLYMSPROD01"]
        assert sorted(nombres, key=key) == ["QLYMSPROD01", "QLYMSPROD02", "QBYMSPROD07", "QLYMSPROD11"]

    def test_numero_de_dos_digitos_no_se_confunde_con_texto(self):
        # 11 debe ir despues de 2, no antes (orden numerico, no alfabetico de texto)
        key = get_sort_key("numeric_suffix")
        assert key("QLYMSPROD02") < key("QLYMSPROD11")

    def test_sin_numero_al_final_queda_al_final(self):
        key = get_sort_key("numeric_suffix")
        nombres = ["APIMAN-FASE1", "SERVIDOR-SIN-NUMERO", "QLYMSPROD01"]
        assert sorted(nombres, key=key)[-1] == "SERVIDOR-SIN-NUMERO"


class TestAlphabeticalStrategy:
    def test_ordena_alfabeticamente(self):
        key = get_sort_key("alphabetical")
        nombres = ["SERVIDOR-B", "SERVIDOR-A", "APIMAN-FASE1"]
        assert sorted(nombres, key=key) == ["APIMAN-FASE1", "SERVIDOR-A", "SERVIDOR-B"]


class TestGetSortKey:
    def test_estrategia_desconocida_cae_a_alphabetical(self):
        key = get_sort_key("no_existe")
        nombres = ["B", "A"]
        assert sorted(nombres, key=key) == ["A", "B"]
