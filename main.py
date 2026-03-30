from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import requests
import time
import os
import pathlib

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

OHIO_CITIES = [
    "Akron","Alliance","Ashland","Ashtabula","Athens","Austintown","Avon","Avon Lake",
    "Barberton","Beavercreek","Bowling Green","Brook Park","Brooklyn","Canton",
    "Chillicothe","Cincinnati","Cleveland","Cleveland Heights","Columbus","Cuyahoga Falls",
    "Dayton","Delaware","Dublin","East Cleveland","Elyria","Euclid","Fairborn","Fairfield",
    "Findlay","Forest Park","Gahanna","Garfield Heights","Green","Grove City","Hamilton",
    "Hilliard","Huber Heights","Hudson","Kent","Kettering","Lakewood","Lancaster","Lima",
    "Lorain","Mansfield","Maple Heights","Marion","Massillon","Medina","Mentor","Miamisburg",
    "Middletown","Newark","New Philadelphia","North Olmsted","North Ridgeville","North Royalton",
    "Norwood","Parma","Parma Heights","Perrysburg","Pickerington","Reynoldsburg","Riverside",
    "Rocky River","Sandusky","Shaker Heights","Solon","South Euclid","Springfield",
    "Stow","Strongsville","Sylvania","Toledo","Trotwood","Troy","Twinsburg",
    "Upper Arlington","Wadsworth","Warren","Westerville","Westlake","Willoughby",
    "Wooster","Xenia","Youngstown","Zanesville",
    "Blacklick","Groveport","Canal Winchester","Obetz","Lithopolis","Pataskala",
    "Granville","Heath","Hebron","Johnstown","Kirkersville","Mifflin","New Albany",
    "Powell","Sunbury","Worthington","Whitehall","Bexley","Clintonville","Marble Cliff",
    "Minerva Park","Riverlea","Urbancrest","Valleyview","Harrisburg","Orient",
    "Plain City","Richwood","Unionville Center","West Jefferson","West Liberty",
]

OHIO_CITIES_LOWER = {c.lower(): c for c in OHIO_CITIES}

class AddressItem(BaseModel):
    id: str
    address: str

class BatchRequest(BaseModel):
    addresses: list[AddressItem]

def geocode_nominatim(address: str) -> str | None:
    """Use Nominatim to geocode an address and return the city."""
    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            "q": address,
            "format": "json",
            "addressdetails": 1,
            "limit": 1,
            "countrycodes": "us"
        }
        headers = {"User-Agent": "OhioCitiesGeocoder/1.0 (real-estate-tool)"}
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data:
                addr = data[0].get("address", {})
                city = (
                    addr.get("city") or
                    addr.get("town") or
                    addr.get("village") or
                    addr.get("municipality") or
                    addr.get("suburb") or
                    addr.get("county", "").replace(" County", "")
                )
                return city
    except Exception as e:
        print(f"Nominatim error for '{address}': {e}")
    return None

@app.get("/")
def root():
    html_path = pathlib.Path(__file__).parent / "index.html"
    if html_path.exists():
        return HTMLResponse(html_path.read_text())
    return {"status": "Ohio Cities Geocoder API is running ✅"}

@app.get("/health")
def health():
    return {"status": "Ohio Cities Geocoder API is running ✅"}

@app.post("/geocode/batch")
def geocode_batch(req: BatchRequest):
    results = {}
    errors = []

    for item in req.addresses:
        addr = item.address.strip()
        city = geocode_nominatim(addr)
        if city:
            city_lower = city.lower()
            # Try exact match
            if city_lower in OHIO_CITIES_LOWER:
                results[item.id] = OHIO_CITIES_LOWER[city_lower]
            else:
                # Try partial match
                matched = None
                for ohio_city_lower, ohio_city in OHIO_CITIES_LOWER.items():
                    if ohio_city_lower in city_lower or city_lower in ohio_city_lower:
                        matched = ohio_city
                        break
                if matched:
                    results[item.id] = matched
                else:
                    # Return the city even if not in Ohio list (frontend can decide)
                    results[item.id] = city
        else:
            errors.append(item.id)
        
        time.sleep(1.1)  # Nominatim rate limit: 1 req/sec

    return {"results": results, "errors": errors}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
