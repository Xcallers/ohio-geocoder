from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import requests
import io
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

MARKET_CITIES = [
    {"keyword": "COLUMBUS",    "priority": 1},
    {"keyword": "NEWARK",      "priority": 2},
    {"keyword": "DELAWARE",    "priority": 3},
    {"keyword": "MARION",      "priority": 4},
    {"keyword": "DAYTON",      "priority": 5},
    {"keyword": "SPRINGFIELD", "priority": 6},
    {"keyword": "CINCINNATI",  "priority": 7},
    {"keyword": "CLEVELAND",   "priority": 8},
]

CENSUS_URL = "https://geocoding.geo.census.gov/geocoder/locations/addressbatch"


def assign_priority(city: str) -> int:
    city_up = city.upper()
    for mc in MARKET_CITIES:
        if mc["keyword"] in city_up:
            return mc["priority"]
    return 9


def census_batch_geocode(addresses: list) -> dict:
    lines = []
    for a in addresses:
        addr = a["address"].replace('"', '').replace('\n', ' ')
        lines.append('{},"{}",,,""\n'.format(a["id"], addr))
    csv_content = "".join(lines)
    files = {
        "addressFile": ("addresses.csv", io.StringIO(csv_content), "text/csv"),
        "benchmark": (None, "Public_AR_Current"),
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
        row_id = parts[0].strip().strip('"')
        match_flag = parts[2].strip().strip('"').upper()
        matched_addr = parts[4].strip().strip('"')
        if match_flag == "MATCH" and matched_addr:
            seg = matched_addr.split(",")
            if len(seg) >= 2:
                results[row_id] = seg[1].strip().title()
    return results


class AddressItem(BaseModel):
    id: str
    address: str


class BatchRequest(BaseModel):
    addresses: list[AddressItem]


@app.get("/", response_class=HTMLResponse)
def serve_frontend():
    html_path = os.path.join(os.path.dirname(__file__), "index.html")
    with open(html_path, encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.post("/geocode/batch")
def geocode_batch(req: BatchRequest):
    input_list = [{"id": item.id, "address": item.address} for item in req.addresses]
    raw = census_batch_geocode(input_list)
    if "error" in raw:
        return {"error": raw["error"], "results": {}, "errors": []}
    results = {}
    errors = []
    for item in req.addresses:
        city = raw.get(item.id)
        if city:
            results[item.id] = {"city": city, "priority": assign_priority(city)}
        else:
            errors.append(item.id)
    return {"results": results, "errors": errors}


@app.get("/health")
def health():
    return {"ok": True}
