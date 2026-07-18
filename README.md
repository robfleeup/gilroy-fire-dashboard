# Gilroy Fire Operations — Version 1

Version 1 is a clean, static rebuild.

## Included

- Gilroy Fire branding and logo
- Rotating department hero photographs
- Six empty KPI tiles
- Current Operations layout
- Mobile-responsive design
- `/health` deployment verification route
- No database
- No OurGilroy connection
- No historical CSV calculations
- No inherited application code

## Render setup

Build command:

```bash
pip install -r requirements.txt
```

Start command:

```bash
gunicorn app:app
```

Health check:

```text
/health
```

Do not connect live data until this design is deployed and approved.
