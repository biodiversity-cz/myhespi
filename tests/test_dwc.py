from myhespi.dwc import map_hespi_row_to_dwc


def test_dwc_mapping_basic():
    row = {
        "family": "Rosaceae",
        "genus": "Rosa",
        "species": "canina",
        "infrasp_taxon": "",
        "authority": "L.",
        "collector": "Jan Novák",
        "collector_number": "123",
        "locality": "Brno",
        "geolocation": "49.1951,16.6068",
        "year": "2020",
        "month": "5",
        "day": "2",
    }

    dwc = map_hespi_row_to_dwc(row).to_dict()
    assert dwc["family"] == "Rosaceae"
    assert dwc["verbatimIdentification"] == "Rosa canina L."
    assert dwc["genericName"] == "Rosa"
    assert dwc["specificEpithet"] == "canina"
    assert dwc["verbatimEventDate"] == "2020-05-02"
    assert dwc["verbatimLatitude"] == "49.195100"
    assert dwc["verbatimLongitude"] == "16.606800"
    assert dwc["recordNumber"] == "123"
    assert dwc["verbatimLocality"] == "Brno"
    assert "occurrenceID" not in dwc
    assert "basisOfRecord" not in dwc


def test_dwc_mapping_empty_fields_present():
    row = {"genus": "Sonchus", "species": "oleraceus"}
    dwc = map_hespi_row_to_dwc(row).to_dict()
    assert dwc["verbatimIdentification"] == "Sonchus oleraceus"
    assert dwc["recordNumber"] == ""
    assert dwc["verbatimLocality"] == ""
    assert dwc["verbatimEventDate"] == ""


def test_dwc_mapping_partial_date():
    row = {"year": "1895", "month": "11"}
    dwc = map_hespi_row_to_dwc(row).to_dict()
    assert dwc["verbatimEventDate"] == "1895-11"

    row_year_only = {"year": "1895"}
    dwc2 = map_hespi_row_to_dwc(row_year_only).to_dict()
    assert dwc2["verbatimEventDate"] == "1895"
