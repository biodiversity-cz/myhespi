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
    assert dwc["scientificName"] == "Rosa canina L."
    assert dwc["eventDate"] == "2020-05-02"
    assert dwc["decimalLatitude"] == "49.195100"
    assert dwc["decimalLongitude"] == "16.606800"
    assert dwc["occurrenceID"].startswith("urn:uuid:")


def test_dwc_mapping_with_stable_id():
    row = {"genus": "Sonchus", "species": "oleraceus"}
    fixed_id = "urn:uuid:test-fixed-id"
    dwc = map_hespi_row_to_dwc(row, occurrence_id=fixed_id).to_dict()
    assert dwc["occurrenceID"] == fixed_id
    assert dwc["scientificName"] == "Sonchus oleraceus"
