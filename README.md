# Gilroy Fire Operations — Version 1.6.1 Render Fix

This package preserves the Version 1.6 dashboard and live-data features while fixing the Render/Gunicorn startup error.

## Render settings
- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn app:app`
- Health check: `/health`

The Flask application object is now consistently named `app`, matching the Render start command.

## Safe update rule
Keep `app.py`, `requirements.txt`, and `render.yaml` as the stable backend. Future routine updates should normally be limited to:
- `templates/`
- `static/`
- `data/`

## Included data and features
- Live OurGilroy incident-feed integration
- Current operations tiles
- NWS weather and alerts
- Vegetation-fire activity
- Watch Duty and Smoke Ready California links
- 2024 partial and 2026 YTD First Due exports
- Uploaded GFD incident photographs
