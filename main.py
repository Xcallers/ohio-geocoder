"""
Ohio Cities Geocoder — FastAPI Backend
Deploy on Railway (free tier)
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
import io
import re

app = FastAPI(title="Ohio Cities Geocoder API")

# Allow requests from any origin (browser)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

MARKET_CITIES = [
    {"keyword": "COLUMBUS",    "display": "Columbus",    "priority": 1},
    {"keyword": "NEWARK",      "display": "Newark, OH",  "priority": 2},
    {"keyword": "DELAWARE",    "display": "Delaware",    "priority": 3},
    {"keyword": "MARION",      "display": "Marion",      "priority": 4},
    {"keyword": "DAYTON",      "display": "Dayton",      "priority": 5},
    {"keyword": "SPRINGFIELD", "display": "Springfield", "priority": 6},
    {"keyword": "CINCINNATI",  "display": "Cincinnati",  "priority": 7},
    {"keyword": "CLEVELAND",   "display": "Cleveland",   "priority": 8},
]

CENSUS_URL = "https://geocoding.geo.census.gov/geocoder/locations/addressbatch"


def assign_priority(city: str) -> int:
    city_up = city.upper()
    for mc in MARKET_CITIES:
        if mc["keyword"] in city_up:
            return mc["priority"]
    return 9


def census_batch_geocode(addresses: list[dict]) -> dict:
    """addresses: [{"id": "0", "address": "123 Main St, OH"}]"""
    lines = []
    for a in addresses:
        addr = a["address"].replace('"', '').replace('\n', ' ')
        lines.append(f'{a["id"]},"{addr}",,,""\n')

    csv_content = "".join(lines)
    files = {
        "addressFile": ("addresses.csv", io.StringIO(csv_content), "text/csv"),
        "benchmark":   (None, "Public_AR_Current"),
    }

    try:
        resp = requests.post(CENSUS_URL, files=files, timeout=120)
        resp.raise_for_status()
    except Exception as e:
        return {"error": str(e)}

    results = {}
    for line in resp.text.strip().splitlines():
        parts = line.split(",")
        if len(parts) < 6:
            continue
        row_id      = parts[0].strip().strip('"')
        match_flag  = parts[2].strip().strip('"').upper()
        matched_addr = parts[4].strip().strip('"')
        if match_flag == "MATCH" and matched_addr:
            seg = matched_addr.split(",")
            if len(seg) >= 2:
                results[row_id] = seg[1].strip().title()

    return results


# ── Models ────────────────────────────────────────────────────────────────────

class AddressItem(BaseModel):
    id: str
    address: str

class BatchRequest(BaseModel):
    addresses: list[AddressItem]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"status": "Ohio Cities Geocoder API is running ✅"}


@app.post("/geocode/batch")
def geocode_batch(req: BatchRequest):
    """
    POST /geocode/batch
    Body: {"addresses": [{"id": "0", "address": "123 Main St Vandalia OH 45377"}, ...]}
    Returns: {"results": {"0": {"city": "Vandalia", "priority": 5}}, "errors": [...]}
    """
    input_list = [{"id": item.id, "address": item.address} for item in req.addresses]
    raw = census_batch_geocode(input_list)

    if "error" in raw:
        return {"error": raw["error"], "results": {}, "errors": []}

    results = {}
    errors  = []
    for item in req.addresses:
        city = raw.get(item.id)
        if city:
            results[item.id] = {
                "city":     city,
                "priority": assign_priority(city),
            }
        else:
            errors.append(item.id)

    return {"results": results, "errors": errors}


@app.get("/health")
def health():
    return {"ok": True}
