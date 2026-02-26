from __future__ import annotations

import csv
import uuid
from dataclasses import dataclass
from datetime import date
from pathlib import Path


@dataclass(frozen=True)
class DwcRecord:
    occurrence_id: str
    basis_of_record: str
    family: str
    genus: str
    specific_epithet: str
    infraspecific_epithet: str
    scientific_name_authorship: str
    scientific_name: str
    recorded_by: str
    record_number: str
    locality: str
    event_date: str
    decimal_latitude: str
    decimal_longitude: str

    def to_dict(self) -> dict[str, str]:
        return {
            "occurrenceID": self.occurrence_id,
            "basisOfRecord": self.basis_of_record,
            "family": self.family,
            "genus": self.genus,
            "specificEpithet": self.specific_epithet,
            "infraspecificEpithet": self.infraspecific_epithet,
            "scientificNameAuthorship": self.scientific_name_authorship,
            "scientificName": self.scientific_name,
            "recordedBy": self.recorded_by,
            "recordNumber": self.record_number,
            "locality": self.locality,
            "eventDate": self.event_date,
            "decimalLatitude": self.decimal_latitude,
            "decimalLongitude": self.decimal_longitude,
        }


def map_hespi_row_to_dwc(row: dict, occurrence_id: str = "") -> DwcRecord:
    if not occurrence_id:
        occurrence_id = f"urn:uuid:{uuid.uuid4()}"

    genus = _txt(row.get("genus"))
    species = _txt(row.get("species"))
    infrasp = _txt(row.get("infrasp_taxon"))
    authority = _txt(row.get("authority"))

    scientific_name = " ".join(part for part in [genus, species, infrasp, authority] if part)

    lat, lon = _parse_geolocation(_txt(row.get("geolocation")))

    return DwcRecord(
        occurrence_id=occurrence_id,
        basis_of_record="PreservedSpecimen",
        family=_txt(row.get("family")),
        genus=genus,
        specific_epithet=species,
        infraspecific_epithet=infrasp,
        scientific_name_authorship=authority,
        scientific_name=scientific_name,
        recorded_by=_txt(row.get("collector")),
        record_number=_txt(row.get("collector_number")),
        locality=_txt(row.get("locality")),
        event_date=_event_date(
            _txt(row.get("year")), _txt(row.get("month")), _txt(row.get("day"))
        ),
        decimal_latitude=lat,
        decimal_longitude=lon,
    )


def write_dwc_csv(path: Path, record: DwcRecord) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    row = record.to_dict()
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row.keys()))
        writer.writeheader()
        writer.writerow(row)


def _txt(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value != value:  # NaN check
        return ""
    return str(value).strip()


def _event_date(year: str, month: str, day: str) -> str:
    if not year:
        return ""
    try:
        y = int(year)
    except ValueError:
        return ""

    if not month:
        return f"{y:04d}"

    try:
        m = int(month)
    except ValueError:
        return f"{y:04d}"

    if not day:
        return f"{y:04d}-{m:02d}"

    try:
        d = int(day)
        return date(y, m, d).isoformat()
    except ValueError:
        return f"{y:04d}-{m:02d}"


def _parse_geolocation(value: str) -> tuple[str, str]:
    if not value:
        return "", ""
    for separator in (",", ";", "|", " "):
        parts = [p for p in value.split(separator) if p]
        if len(parts) == 2:
            lat = _to_decimal(parts[0])
            lon = _to_decimal(parts[1])
            if lat and lon:
                return lat, lon
    return "", ""


def _to_decimal(text: str) -> str:
    cleaned = text.strip().replace(",", ".")
    try:
        return f"{float(cleaned):.6f}"
    except ValueError:
        return ""
