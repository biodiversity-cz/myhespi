from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path


@dataclass(frozen=True)
class DwcRecord:
    verbatim_identification: str
    family: str
    generic_name: str
    specific_epithet: str
    infraspecific_epithet: str
    scientific_name_authorship: str
    recorded_by: str
    record_number: str
    verbatim_locality: str
    verbatim_event_date: str
    verbatim_latitude: str
    verbatim_longitude: str

    def to_dict(self) -> dict[str, str]:
        return {
            "verbatimIdentification": self.verbatim_identification,
            "family": self.family,
            "genericName": self.generic_name,
            "specificEpithet": self.specific_epithet,
            "infraspecificEpithet": self.infraspecific_epithet,
            "scientificNameAuthorship": self.scientific_name_authorship,
            "recordedBy": self.recorded_by,
            "recordNumber": self.record_number,
            "verbatimLocality": self.verbatim_locality,
            "verbatimEventDate": self.verbatim_event_date,
            "verbatimLatitude": self.verbatim_latitude,
            "verbatimLongitude": self.verbatim_longitude,
        }


def map_hespi_row_to_dwc(row: dict) -> DwcRecord:
    genus = _txt(row.get("genus"))
    species = _txt(row.get("species"))
    infrasp = _txt(row.get("infrasp_taxon"))
    authority = _txt(row.get("authority"))

    verbatim_id = " ".join(part for part in [genus, species, infrasp, authority] if part)

    lat, lon = _parse_geolocation(_txt(row.get("geolocation")))

    return DwcRecord(
        verbatim_identification=verbatim_id,
        family=_txt(row.get("family")),
        generic_name=genus,
        specific_epithet=species,
        infraspecific_epithet=infrasp,
        scientific_name_authorship=authority,
        recorded_by=_txt(row.get("collector")),
        record_number=_txt(row.get("collector_number")),
        verbatim_locality=_txt(row.get("locality")),
        verbatim_event_date=_event_date(
            _txt(row.get("year")), _txt(row.get("month")), _txt(row.get("day"))
        ),
        verbatim_latitude=lat,
        verbatim_longitude=lon,
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
    """Compose ISO-8601 date from individual parts (YYYY, YYYY-MM, or YYYY-MM-DD)."""
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
