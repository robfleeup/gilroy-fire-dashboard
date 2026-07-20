# Annual Report Viewer Update

This repository includes the live Gilroy Fire Operations Dashboard and the 2025 Annual Performance Report.

## New dashboard links

- Dashboard navigation: **2025 Annual Report**
- Dashboard feature card: **View Interactive Report**
- Report URL: `/annual-report`

## Viewer controls

- Previous/next buttons
- Keyboard left/right arrows, Page Up/Page Down, Home and End
- Touch swipe on phones and tablets
- Mouse-wheel navigation
- Chapter menu
- Full-screen button
- Printable PDF

## Render deployment

Upload the complete contents of this repository to GitHub. Do not upload the outer folder itself.

Recommended Render settings:

```text
Build command: pip install -r requirements.txt
Start command: gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --timeout 60
Health check: /health
```

Both `gunicorn app:app` and `gunicorn app:APP` are supported.

After committing the files, use **Clear build cache & deploy** in Render.
