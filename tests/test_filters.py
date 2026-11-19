import pytest

from conftest import HEADER, make_row
from offcatalog.config import Config
from offcatalog.filters import RowFilter


@pytest.fixture
def flt(tmp_path):
    return RowFilter(HEADER, Config(work_dir=tmp_path, output_dir=tmp_path))


def run(flt, **kw):
    return flt.process(make_row(**kw).split("\t"))


def test_prodotto_valido(flt):
    rec, reason = run(flt)
    assert reason is None
    assert rec[0] == "8000000000017" and rec[1] == "Biscotti frollini" and rec[2] == "Marca Uno"
    assert rec[3] == 480.0 and rec[12] == 30.0 and rec[13] == "c" and rec[14] == 4


def test_scarto_paese(flt):
    assert run(flt, countries_tags="en:france,en:spain")[1] == "paese"
    assert run(flt, countries_tags="en:france,en:italy")[1] is None


@pytest.mark.parametrize("code", ["", "abc", "1234567", "123456789012345", "80000 000017"])
def test_scarto_barcode(flt, code):
    assert run(flt, code=code)[1] == "barcode"


def test_scarto_nome(flt):
    assert run(flt, product_name="  ")[1] == "nome"


def test_nome_italiano_se_presente(tmp_path):
    header = HEADER + ["product_name_it"]
    f = RowFilter(header, Config(work_dir=tmp_path, output_dir=tmp_path))
    rec, _ = f.process(make_row(header, product_name_it="Nome IT").split("\t"))
    assert rec[1] == "Nome IT"
    rec, _ = f.process(make_row(header, product_name_it="").split("\t"))
    assert rec[1] == "Biscotti frollini"


@pytest.mark.parametrize("kcal", ["0", "0.5", "901", "5000", "abc", ""])
def test_scarto_kcal(flt, kcal):
    assert run(flt, **{"energy-kcal_100g": kcal, "energy_100g": ""})[1] == "kcal"


def test_kj_convertiti_in_kcal(flt):
    rec, reason = run(flt, **{"energy-kcal_100g": "", "energy_100g": "2008", "fat_100g": "", "proteins_100g": ""})
    assert reason is None and rec[3] == pytest.approx(2008 / 4.184, abs=0.1)
    rec, _ = run(flt, **{"energy-kcal_100g": "", "energy-kj_100g": "1000", "energy_100g": "9999", "fat_100g": "", "proteins_100g": ""})
    assert rec[3] == pytest.approx(239.0, abs=0.1)  # preferisce energy-kj_100g


def test_coerenza_macro(flt):
    # kJ scritti come kcal: 880 dichiarate, macro dicono ~105
    assert run(flt, **{"energy-kcal_100g": "880", "fat_100g": "5", "carbohydrates_100g": "10", "proteins_100g": "5"})[1] == "coerenza"
    # macro assenti: nessun controllo di coerenza
    assert run(flt, **{"energy-kcal_100g": "880", "fat_100g": ""})[1] is None
    # dentro la tolleranza
    assert run(flt, **{"energy-kcal_100g": "500"})[1] is None  # calc 9*20+4*65+4*7 = 468
    # macro fuori scala
    assert run(flt, fat_100g="140")[1] == "coerenza"


def test_alcol_conta_nella_coerenza(flt):
    r = run(flt, **{"energy-kcal_100g": "230", "fat_100g": "0", "carbohydrates_100g": "0",
                     "proteins_100g": "0", "alcohol_100g": "33"})
    assert r[1] is None


def test_sale_da_sodio_e_valori_non_noti(flt):
    rec, _ = run(flt, salt_100g="", sodium_100g="0.4")
    assert rec[10] == 1.0
    rec, _ = run(flt, fiber_100g="abc", serving_quantity="-4", nutriscore_grade="unknown", nova_group="9")
    assert rec[8] is None and rec[12] is None and rec[13] is None and rec[14] is None


def test_colonne_obbligatorie(tmp_path):
    with pytest.raises(ValueError):
        RowFilter(["code", "product_name"], Config(work_dir=tmp_path, output_dir=tmp_path))
