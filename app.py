
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from flask import Flask, jsonify, render_template, send_from_directory

APP = Flask(__name__)

DB_PATH = os.getenv("DASHBOARD_DB", "/tmp/gilroy_fire.db")
AGENCY_ID = os.getenv("PULSEPOINT_AGENCY_ID", "43010")
OURGILROY_API = os.getenv(
    "OURGILROY_API",
    "https://ourgilroy.com/api/fire.php"
).strip()
SYNC_MIN_SECONDS = int(os.getenv("SYNC_MIN_SECONDS", "180"))

GILROY_LAT = 37.0058
GILROY_LON = -121.5683

SYNC_LOCK = threading.Lock()
LAST_SYNC_AT = 0.0
LAST_SYNC_RESULT = {"mode": "not_started", "saved": 0}

GILROY_DISPLAY_UNITS = {
    "E47", "E48", "E49", "E50",
    "RM49", "E650", "T47",
    "B47", "B48", "B49", "B50",
}

KNOWN_UNITS = {
    "E47": {"type": "Engine", "station": "47"},
    "E48": {"type": "Engine", "station": "48"},
    "E49": {"type": "Engine", "station": "49"},
    "E50": {"type": "Engine", "station": "50"},
    "E650": {"type": "Engine", "station": "Support"},
    "E348": {"type": "Reserve Engine", "station": "Reserve"},
    "T47": {"type": "Truck", "station": "47"},
    "RM49": {"type": "Rescue Medic", "station": "49"},
    "B47": {"type": "Chief Officer", "station": "Command"},
    "B48": {"type": "Chief Officer", "station": "Command"},
    "B49": {"type": "Chief Officer", "station": "Command"},
    "B50": {"type": "Chief Officer", "station": "Command"},
}

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS incidents (
            incident_id TEXT PRIMARY KEY,
            received_at TEXT NOT NULL,
            incident_type TEXT,
            call_type TEXT,
            category TEXT,
            address TEXT,
            latitude REAL,
            longitude REAL,
            status TEXT,
            is_active INTEGER NOT NULL DEFAULT 0,
            closed_at TEXT,
            duration_minutes INTEGER,
            source_updated_at TEXT,
            raw_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS unit_responses (
            incident_id TEXT NOT NULL,
            unit_id TEXT NOT NULL,
            unit_type TEXT NOT NULL,
            station TEXT,
            received_at TEXT NOT NULL,
            PRIMARY KEY (incident_id, unit_id)
        );

        CREATE INDEX IF NOT EXISTS idx_inc_received ON incidents(received_at);
        CREATE INDEX IF NOT EXISTS idx_inc_active ON incidents(is_active);
        CREATE INDEX IF NOT EXISTS idx_unit_received ON unit_responses(received_at);
        CREATE INDEX IF NOT EXISTS idx_unit_id ON unit_responses(unit_id);
        """)

def get_json(url: str):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "GilroyFireOperations/1.0 public-dashboard",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=25) as response:
        return json.load(response)

def normalize_dt(value):
    if not value:
        return None
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text).isoformat()
    except ValueError:
        try:
            return datetime.strptime(text, "%Y-%m-%d %H:%M:%S").isoformat()
        except ValueError:
            return None

def classify_unit(unit_id: str):
    unit = (unit_id or "").strip().upper()
    if unit in KNOWN_UNITS:
        return KNOWN_UNITS[unit]
    if unit.startswith("RM"):
        return {"type": "Rescue Medic", "station": ""}
    if unit.startswith("WT"):
        return {"type": "Water Tender", "station": ""}
    if unit.startswith("M") and unit[1:].isdigit():
        return {"type": "ALS Ambulance", "station": "Ambulance Provider"}
    if unit.startswith("A") and unit[1:].isdigit():
        return {"type": "BLS Ambulance", "station": "Ambulance Provider"}
    if unit.startswith("B") and unit[1:].isdigit():
        return {"type": "Chief Officer", "station": "Command"}
    if unit.startswith("E") and unit[1:].isdigit():
        return {"type": "Engine", "station": ""}
    if unit.startswith("T") and unit[1:].isdigit():
        return {"type": "Truck", "station": ""}
    if unit == "GI":
        return {"type": "Gilroy Fire", "station": ""}
    return {"type": "Other", "station": ""}

def split_units(value):
    if not value:
        return []
    if isinstance(value, list):
        raw = value
    else:
        raw = str(value).replace(";", ",").split(",")
    return sorted({str(u).strip().upper() for u in raw if str(u).strip()})

def save_rows(rows):
    saved = 0
    with db() as conn:
        for raw in rows:
            if not isinstance(raw, dict):
                continue
            incident_id = str(raw.get("incident_id") or "").strip()
            if not incident_id:
                fingerprint = "|".join([
                    str(raw.get("received_at") or ""),
                    str(raw.get("call_type_name") or ""),
                    str(raw.get("address") or ""),
                ])
                incident_id = hashlib.sha256(fingerprint.encode()).hexdigest()[:24]

            received = normalize_dt(raw.get("received_at")) or datetime.now().isoformat()
            closed = normalize_dt(raw.get("closed_at"))
            is_active = 1 if raw.get("is_active") else 0
            status = "Active" if is_active else "Closed"

            conn.execute("""
                INSERT INTO incidents (
                    incident_id, received_at, incident_type, call_type, category,
                    address, latitude, longitude, status, is_active, closed_at,
                    duration_minutes, source_updated_at, raw_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(incident_id) DO UPDATE SET
                    incident_type=excluded.incident_type,
                    call_type=excluded.call_type,
                    category=excluded.category,
                    address=excluded.address,
                    latitude=excluded.latitude,
                    longitude=excluded.longitude,
                    status=excluded.status,
                    is_active=excluded.is_active,
                    closed_at=excluded.closed_at,
                    duration_minutes=excluded.duration_minutes,
                    source_updated_at=excluded.source_updated_at,
                    raw_json=excluded.raw_json
            """, (
                incident_id, received,
                raw.get("call_type_name") or raw.get("call_type") or "Unknown",
                raw.get("call_type"),
                raw.get("category"),
                raw.get("address"),
                raw.get("lat"),
                raw.get("lng"),
                status,
                is_active,
                closed,
                raw.get("duration_min"),
                datetime.now(timezone.utc).isoformat(),
                json.dumps(raw, separators=(",", ":")),
            ))

            current_units = split_units(raw.get("units"))
            conn.execute("DELETE FROM unit_responses WHERE incident_id=?", (incident_id,))
            for unit in current_units:
                meta = classify_unit(unit)
                conn.execute("""
                    INSERT OR IGNORE INTO unit_responses
                    (incident_id, unit_id, unit_type, station, received_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (incident_id, unit, meta["type"], meta["station"], received))
            saved += 1
    return saved

def fetch_all_incidents(force=False):
    global LAST_SYNC_AT, LAST_SYNC_RESULT
    now = time.time()
    if not force and now - LAST_SYNC_AT < SYNC_MIN_SECONDS:
        return {**LAST_SYNC_RESULT, "cached": True}

    with SYNC_LOCK:
        now = time.time()
        if not force and now - LAST_SYNC_AT < SYNC_MIN_SECONDS:
            return {**LAST_SYNC_RESULT, "cached": True}

        first_params = {
            "view": "incidents",
            "q": "",
            "category": "",
            "type": "",
            "from": "",
            "to": "",
            "active": "0",
            "page": "1",
            "per_page": "100",
            "sort": "received",
            "dir": "desc",
        }
        first_url = OURGILROY_API + "?" + urllib.parse.urlencode(first_params)
        first = get_json(first_url)
        total_pages = int(first.get("pages") or 1)
        rows = list(first.get("rows") or [])

        for page in range(2, total_pages + 1):
            params = dict(first_params)
            params["page"] = str(page)
            url = OURGILROY_API + "?" + urllib.parse.urlencode(params)
            payload = get_json(url)
            rows.extend(payload.get("rows") or [])

        saved = save_rows(rows)
        LAST_SYNC_AT = time.time()
        LAST_SYNC_RESULT = {
            "mode": "live",
            "source": "OurGilroy public incident API",
            "saved": saved,
            "received": len(rows),
            "pages": total_pages,
            "source_total": first.get("total"),
            "synced_at": datetime.now(timezone.utc).isoformat(),
        }
        return LAST_SYNC_RESULT

def period_values():
    now = datetime.now().astimezone()
    return now.strftime("%Y-%m-%d"), now.strftime("%Y-%m"), now.strftime("%Y")

@APP.route("/")
def home():
    return render_template("index.html", agency_id=AGENCY_ID)

@APP.route("/api/sync", methods=["POST"])
def sync():
    try:
        return jsonify(fetch_all_incidents())
    except Exception as exc:
        return jsonify({"mode": "error", "message": str(exc)}), 502

@APP.route("/api/metrics")
def metrics():
    try:
        fetch_all_incidents()
    except Exception:
        pass

    today, month, year = period_values()
    with db() as conn:
        summary = {}
        for label, value in (("today", today), ("month", month), ("ytd", year)):
            n = len(value)
            incidents = conn.execute(
                f"SELECT COUNT(*) FROM incidents WHERE substr(received_at,1,{n})=?",
                (value,),
            ).fetchone()[0]
            active = conn.execute(
                f"SELECT COUNT(*) FROM incidents WHERE substr(received_at,1,{n})=? AND is_active=1",
                (value,),
            ).fetchone()[0]
            placeholders = ",".join("?" for _ in GILROY_DISPLAY_UNITS)
            unit_responses = conn.execute(
                f"""SELECT COUNT(*) FROM unit_responses
                    WHERE substr(received_at,1,{n})=?
                    AND unit_id IN ({placeholders})""",
                (value, *sorted(GILROY_DISPLAY_UNITS)),
            ).fetchone()[0]
            by_type = {
                row["unit_type"]: row["c"]
                for row in conn.execute(
                    f"""SELECT unit_type, COUNT(*) c
                        FROM unit_responses
                        WHERE substr(received_at,1,{n})=?
                        GROUP BY unit_type""",
                    (value,),
                )
            }
            summary[label] = {
                "incidents": incidents,
                "active": active,
                "unit_responses": unit_responses,
                "engine_responses": by_type.get("Engine", 0) + by_type.get("Reserve Engine", 0),
                "truck_responses": by_type.get("Truck", 0),
                "rescue_medic_responses": by_type.get("Rescue Medic", 0),
                "chief_responses": by_type.get("Chief Officer", 0),
                "als_ambulance_responses": by_type.get("ALS Ambulance", 0),
                "bls_ambulance_responses": by_type.get("BLS Ambulance", 0),
                "water_tender_responses": by_type.get("Water Tender", 0),
                "gilroy_fire_responses": by_type.get("Gilroy Fire", 0),
            }

        placeholders = ",".join("?" for _ in GILROY_DISPLAY_UNITS)
        unit_rows = conn.execute(f"""
            SELECT
                unit_id, unit_type, station,
                SUM(CASE WHEN substr(received_at,1,10)=? THEN 1 ELSE 0 END) today,
                SUM(CASE WHEN substr(received_at,1,7)=? THEN 1 ELSE 0 END) month,
                SUM(CASE WHEN substr(received_at,1,4)=? THEN 1 ELSE 0 END) ytd
            FROM unit_responses
            WHERE unit_id IN ({placeholders})
            GROUP BY unit_id, unit_type, station
            ORDER BY ytd DESC, unit_id
        """, (today, month, year, *sorted(GILROY_DISPLAY_UNITS))).fetchall()

        categories = [
            dict(r) for r in conn.execute("""
                SELECT category, COUNT(*) count
                FROM incidents
                WHERE substr(received_at,1,4)=?
                GROUP BY category
                ORDER BY count DESC
            """, (year,))
        ]

        duration = conn.execute("""
            SELECT
                COUNT(duration_minutes) n,
                ROUND(AVG(duration_minutes),1) mean
            FROM incidents
            WHERE duration_minutes IS NOT NULL
        """).fetchone()

    return jsonify({
        "generated_at": datetime.now().astimezone().isoformat(),
        "feed_configured": True,
        "source": "OurGilroy public incident API",
        "summary": summary,
        "units": [dict(row) for row in unit_rows],
        "categories": categories,
        "duration": dict(duration),
        "last_sync": LAST_SYNC_RESULT,
    })

@APP.route("/api/recent")
def recent():
    try:
        fetch_all_incidents()
    except Exception:
        pass

    with db() as conn:
        placeholders = ",".join("?" for _ in GILROY_DISPLAY_UNITS)
        rows = conn.execute(f"""
            SELECT
                i.incident_id, i.received_at, i.incident_type, i.category,
                i.address, i.status, i.is_active, i.duration_minutes,
                (
                    SELECT GROUP_CONCAT(ur.unit_id, ', ')
                    FROM unit_responses ur
                    WHERE ur.incident_id=i.incident_id
                    AND ur.unit_id IN ({placeholders})
                ) units
            FROM incidents i
            ORDER BY datetime(i.received_at) DESC
            LIMIT 50
        """, tuple(sorted(GILROY_DISPLAY_UNITS))).fetchall()
    return jsonify([dict(row) for row in rows])


@APP.route("/api/firstdue-snapshot")
def firstdue_snapshot():
    return send_from_directory(APP.static_folder, "firstdue-2026.json", mimetype="application/json")


@APP.route("/api/current-operations")
def current_operations():
    try:
        fetch_all_incidents()
    except Exception:
        pass

    today, _, _ = period_values()
    now_local = datetime.now().astimezone()

    fire_keywords = (
        "fire", "smoke", "hazard", "explosion", "alarm",
        "vehicle accident", "traffic collision", "rescue"
    )

    with db() as conn:
        today_rows = conn.execute("""
            SELECT incident_id, received_at, incident_type, category,
                   address, is_active, duration_minutes
            FROM incidents
            WHERE substr(received_at,1,10)=?
            ORDER BY datetime(received_at) DESC
        """, (today,)).fetchall()

        active_rows = conn.execute("""
            SELECT incident_id, received_at, incident_type, category,
                   address, is_active, duration_minutes
            FROM incidents
            WHERE is_active=1
            ORDER BY datetime(received_at) DESC
        """).fetchall()

        active_ids = [r["incident_id"] for r in active_rows]
        gilroy_units = []
        chief_units = []
        als_units = []
        bls_units = []

        if active_ids:
            incident_placeholders = ",".join("?" for _ in active_ids)
            display_placeholders = ",".join("?" for _ in GILROY_DISPLAY_UNITS)

            gilroy_units = [
                r["unit_id"] for r in conn.execute(f"""
                    SELECT DISTINCT unit_id
                    FROM unit_responses
                    WHERE incident_id IN ({incident_placeholders})
                    AND unit_id IN ({display_placeholders})
                    ORDER BY unit_id
                """, (*active_ids, *sorted(GILROY_DISPLAY_UNITS)))
            ]

            chief_units = [u for u in gilroy_units if u in {"B47","B48","B49","B50"}]

            all_active_units = [
                r["unit_id"] for r in conn.execute(f"""
                    SELECT DISTINCT unit_id
                    FROM unit_responses
                    WHERE incident_id IN ({incident_placeholders})
                    ORDER BY unit_id
                """, tuple(active_ids))
            ]
            als_units = [u for u in all_active_units if u.startswith("M") and u[1:].isdigit()]
            bls_units = [u for u in all_active_units if u.startswith("A") and u[1:].isdigit()]

        ems_today = 0
        fire_other_today = 0
        for row in today_rows:
            text = f"{row['incident_type'] or ''} {row['category'] or ''}".lower()
            if "medical" in text or "ems" in text:
                ems_today += 1
            elif any(word in text for word in fire_keywords):
                fire_other_today += 1
            else:
                fire_other_today += 1

        longest_active_minutes = 0
        longest_active_type = None
        for row in active_rows:
            received_text = row["received_at"]
            try:
                received_dt = datetime.fromisoformat(received_text)
                if received_dt.tzinfo is None:
                    received_dt = received_dt.replace(tzinfo=now_local.tzinfo)
                minutes = max(0, round((now_local - received_dt.astimezone(now_local.tzinfo)).total_seconds() / 60))
            except Exception:
                minutes = int(row["duration_minutes"] or 0)
            if minutes > longest_active_minutes:
                longest_active_minutes = minutes
                longest_active_type = row["incident_type"]

        active_incidents = []
        for row in active_rows[:8]:
            units = [
                r["unit_id"] for r in conn.execute("""
                    SELECT unit_id
                    FROM unit_responses
                    WHERE incident_id=?
                    ORDER BY unit_id
                """, (row["incident_id"],))
            ]
            active_incidents.append({
                "incident_id": row["incident_id"],
                "received_at": row["received_at"],
                "incident_type": row["incident_type"],
                "category": row["category"],
                "address": row["address"],
                "gilroy_units": [u for u in units if u in GILROY_DISPLAY_UNITS],
                "als_units": [u for u in units if u.startswith("M") and u[1:].isdigit()],
                "bls_units": [u for u in units if u.startswith("A") and u[1:].isdigit()],
            })

    return jsonify({
        "updated_at": now_local.isoformat(),
        "active_incidents": len(active_rows),
        "incidents_today": len(today_rows),
        "ems_today": ems_today,
        "fire_other_today": fire_other_today,
        "gilroy_units_committed": len(gilroy_units),
        "gilroy_unit_ids": gilroy_units,
        "chiefs_committed": len(chief_units),
        "chief_unit_ids": chief_units,
        "als_assigned": len(als_units),
        "als_unit_ids": als_units,
        "bls_assigned": len(bls_units),
        "bls_unit_ids": bls_units,
        "longest_active_minutes": longest_active_minutes,
        "longest_active_type": longest_active_type,
        "active_incident_list": active_incidents,
    })

@APP.route("/api/weather")
def weather():
    try:
        point = get_json(f"https://api.weather.gov/points/{GILROY_LAT},{GILROY_LON}")
        props = point["properties"]
        stations = get_json(props["observationStations"])
        features = stations.get("features", [])
        station_id = features[0]["properties"]["stationIdentifier"] if features else "KWVI"
        observation = get_json(f"https://api.weather.gov/stations/{station_id}/observations/latest")
        hourly = get_json(props["forecastHourly"])
        obs = observation.get("properties", {})
        periods = hourly.get("properties", {}).get("periods", [])
        current = periods[0] if periods else {}

        def c_to_f(value):
            return round(value * 9 / 5 + 32) if isinstance(value, (int, float)) else None

        temp_f = c_to_f((obs.get("temperature") or {}).get("value"))
        humidity = (obs.get("relativeHumidity") or {}).get("value")
        wind_kmh = (obs.get("windSpeed") or {}).get("value")
        gust_kmh = (obs.get("windGust") or {}).get("value")
        return jsonify({
            "temperature_f": temp_f if temp_f is not None else current.get("temperature"),
            "humidity": round(humidity) if isinstance(humidity, (int, float)) else None,
            "wind_mph": round(wind_kmh * 0.621371) if isinstance(wind_kmh, (int, float)) else None,
            "gust_mph": round(gust_kmh * 0.621371) if isinstance(gust_kmh, (int, float)) else None,
            "description": obs.get("textDescription") or current.get("shortForecast"),
        })
    except Exception as exc:
        return jsonify({"error": str(exc)}), 502

@APP.route("/api/alerts")
def alerts():
    try:
        data = get_json(f"https://api.weather.gov/alerts/active?point={GILROY_LAT},{GILROY_LON}")
        output = []
        for feature in data.get("features", [])[:5]:
            p = feature.get("properties", {})
            output.append({
                "event": p.get("event"),
                "headline": p.get("headline"),
                "severity": p.get("severity"),
            })
        return jsonify({"count": len(output), "alerts": output})
    except Exception as exc:
        return jsonify({"error": str(exc), "count": 0, "alerts": []}), 502


@APP.route("/health")
def health():
    return jsonify({"status":"ok","application":"Gilroy Fire Operations","version":"1.6-live-wildland"})

@APP.route("/api/vegetation-activity")
def vegetation_activity():
    return send_from_directory(APP.static_folder, "data/vegetation_activity.json", mimetype="application/json")

init_db()

if __name__ == "__main__":
    APP.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")), debug=True)
