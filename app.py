from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, render_template

APP = Flask(__name__)
BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "data" / "historical.json"
PULSEPOINT_URL = os.getenv(
    "PULSEPOINT_URL",
    "https://ourgilroy.com/api/fire.php?view=incidents"
)

FALLBACK_URL = os.getenv(
    "FALLBACK_URL",
    "https://ourgilroy.com/api/fire.php?view=incidents"
)
LAT, LON = 37.0058, -121.5683


def fetch_json(url: str, timeout: int = 12):
    req = urllib.request.Request(url, headers={"User-Agent": "GilroyFireOperations/3.0", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8-sig"))


def load_historical():
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def parse_incidents(payload):
    rows=[]
    if isinstance(payload, list): rows=payload
    elif isinstance(payload, dict):
        for key in ("incidents","Incidents","items","data","results"):
            value=payload.get(key)
            if isinstance(value,list): rows=value; break
        if not rows:
            for value in payload.values():
                if isinstance(value,list) and value and isinstance(value[0],dict): rows=value; break
    result=[]
    for row in rows:
        if not isinstance(row,dict): continue
        address=row.get("address") or row.get("FullDisplayAddress") or row.get("Address") or row.get("location") or "Location unavailable"
        typ=row.get("type") or row.get("IncidentType") or row.get("CallType") or row.get("dispatch_type") or "Incident"
        units=row.get("units") or row.get("Unit") or row.get("Units") or []
        if isinstance(units,str): units=[u.strip() for u in re.split(r"[,; ]+",units) if u.strip()]
        received=row.get("received_at") or row.get("CallReceivedDateTime") or row.get("DateTime") or row.get("timestamp")
        status=str(row.get("status") or row.get("Status") or "").lower()
        active=bool(row.get("is_active")) or status in {"active","open","dispatched","enroute","on scene"}
        result.append({"id":str(row.get("id") or row.get("IncidentID") or row.get("IncidentId") or ""),"type":str(typ),"address":str(address),"units":units,"received_at":received,"is_active":active})
    return result


def live_incidents():
    errors=[]
    for source,url in (("PulsePoint",PULSEPOINT_URL),("OurGilroy public incident feed",FALLBACK_URL)):
        try:
            rows=parse_incidents(fetch_json(url))
            if rows: return rows,source,None
            errors.append(f"{source}: no incidents returned")
        except Exception as exc: errors.append(f"{source}: {exc}")
    return [],"Unavailable","; ".join(errors)


@APP.get("/")
def home():
    return render_template("index.html")


@APP.get("/annual-report")
def annual_report():
    return render_template("annual-report.html")


@APP.get("/health")
def health():
    return jsonify({"status":"ok","time":datetime.now(timezone.utc).isoformat()})


@APP.get("/api/historical")
@APP.get("/api/firstdue-snapshot")
def historical():
    return jsonify(load_historical())


@APP.get("/api/live")
@APP.get("/api/current-operations")
def live():
    rows,source,error=live_incidents()
    today=datetime.now().astimezone().date()
    def is_today(value):
        if not value: return True
        try: return datetime.fromisoformat(str(value).replace("Z","+00:00")).astimezone().date()==today
        except Exception: return True
    todays=[r for r in rows if is_today(r.get("received_at"))]
    active=[r for r in rows if r.get("is_active")]
    ems=[r for r in todays if re.search(r"medical|ems|cardiac|breathing|injury|sick|fall",r.get("type",""),re.I)]
    unit_ids=sorted({u.upper() for r in active for u in r.get("units",[]) if re.match(r"^(E|T|RM|B)\d+",u.upper())})
    ambulance_ids=sorted({u.upper() for r in active for u in r.get("units",[]) if re.match(r"^[MA]\d+",u.upper())})
    return jsonify({"available":bool(rows),"source":source,"error":error,"updated_at":datetime.now(timezone.utc).isoformat(),"incidents_today":len(todays),"active_incidents":len(active),"ems_today":len(ems),"fire_other_today":max(0,len(todays)-len(ems)),"gilroy_units_committed":len(unit_ids),"gilroy_unit_ids":unit_ids,"chiefs_committed":sum(1 for u in unit_ids if u.startswith("B")),"als_assigned":sum(1 for u in ambulance_ids if u.startswith("M")),"bls_assigned":sum(1 for u in ambulance_ids if u.startswith("A")),"longest_active_minutes":0,"recent":todays[:10]})


@APP.get("/api/weather")
def weather():
    try:
        points=fetch_json(f"https://api.weather.gov/points/{LAT},{LON}")
        props=points["properties"]
        hourly=fetch_json(props["forecastHourly"])["properties"]["periods"][0]
        return jsonify({"available":True,"temperature_f":hourly.get("temperature"),"description":hourly.get("shortForecast"),"wind_mph":hourly.get("windSpeed"),"wind_direction":hourly.get("windDirection"),"humidity":(hourly.get("relativeHumidity") or {}).get("value"),"probability":(hourly.get("probabilityOfPrecipitation") or {}).get("value"),"observed_at":hourly.get("startTime")})
    except Exception as exc:
        return jsonify({"available":False,"error":str(exc)})


@APP.get("/api/alerts")
def alerts():
    try:
        payload=fetch_json(f"https://api.weather.gov/alerts/active?point={LAT},{LON}")
        alerts=[{"event":f.get("properties",{}).get("event"),"headline":f.get("properties",{}).get("headline")} for f in payload.get("features",[])]
        return jsonify({"available":True,"count":len(alerts),"alerts":alerts})
    except Exception as exc:
        return jsonify({"available":False,"count":0,"alerts":[],"error":str(exc)})


# Compatibility with either Render start command: gunicorn app:APP or gunicorn app:app
app = APP


if __name__ == "__main__":
    APP.run(host="0.0.0.0", port=int(os.getenv("PORT","10000")), debug=False)
