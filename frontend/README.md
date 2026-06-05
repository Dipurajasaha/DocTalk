# DocTalk Frontend

Vite + React 19 SPA for the DocTalk patient and doctor portals.

## Scripts

| Command | Description |
|---------|-------------|
| `npm run dev` | Dev server on port 5173 |
| `npm run build` | Production bundle to `dist/` |
| `npm run preview` | Preview the production build |

## Development

```bash
npm install
npm run dev
```

The dev server proxies these paths to `http://127.0.0.1:8000`:

- `/api` (including WebSockets)
- `/health`
- `/static`
- `/me`

Start the FastAPI backend before using the UI.

## API Integration

All backend calls use relative URLs (`/api/...`) via `src/lib/apiClient.js` and `src/lib/api.js`. Authentication uses a Bearer token stored in `localStorage` under `doctalk_token`.

### Main endpoints used

- **Auth:** `/api/auth/patient/*`, `/api/auth/doctor/*`, `/api/me`
- **Appointments:** `/api/appointments/*`
- **Assets:** `/api/assets/*`
- **Chat:** `/api/chat/consultations/*`
- **AI WebSockets:** `/api/chat/ai/patient/ws`, `/api/chat/ai/doctor/ws`
- **Analysis:** `/api/analyze_document`, `/api/analyze_xray`, `/api/explain_report`

## Routes

Defined in `src/App.jsx`:

- `/` — Home
- `/login` — Login and registration
- `/patient/dashboard` — Patient dashboard
- `/doctor/dashboard` — Doctor dashboard
- `/reports/:id` — Report view
- `/prescriptions/:id` — Prescription view

## Production

```bash
npm run build
npm run preview
```

For production deployment, configure your reverse proxy to forward `/api`, `/health`, and `/static` to the backend service.
