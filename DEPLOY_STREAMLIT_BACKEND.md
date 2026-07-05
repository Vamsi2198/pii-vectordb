Deploying the FastAPI backend for Streamlit Cloud (quick guide)

Goal
- Host the backend at a public HTTPS URL so the Streamlit frontend can call API endpoints.

Options
1) Render / Railway / Fly (recommended): push repo to GitHub and create a new service pointing at this repo. Use Docker (recommended) or a Python service.
2) Heroku (deprecated but works): use `Procfile` or Docker.
3) VPS / DigitalOcean: build Docker image and run behind NGINX with TLS.

Quick Render Docker steps
1. Push this repo to GitHub.
2. On Render, create a new Web Service.
   - Connect GitHub repo and select the branch.
   - Use Docker as the environment (Render will build the Dockerfile).
   - Set the health/check port to `8000` (Render sets `PORT` env var automatically).
   - Add environment variables: `PINECONE_API_KEY`, `OPENAI_API_KEY`, `VAULT_SECRET`, `PINECONE_INDEX`, etc.
3. Deploy. Render will give you a public URL like `https://your-app.onrender.com`.

Streamlit Cloud configuration
- In your Streamlit Cloud app settings (where you host the Streamlit app), set a secret named `API_BASE` with the value of your backend URL, e.g. `https://your-app.onrender.com`.
- Restart the Streamlit app.

CORS
- `app.py` already enables CORS for all origins. For production tighten it to only allow your Streamlit domain.

Security
- Serve over HTTPS (Render/Railway provide HTTPS by default).
- Require an `auth_token` for sensitive endpoints and validate it in the backend.

Local testing with Docker

Build and run:
```bash
# From repo root
docker build -t aagcp-backend:local .
docker run -p 8000:8000 -e PORT=8000 -e PINECONE_API_KEY=yourkey aagcp-backend:local
```

Verify endpoints:
```bash
curl https://localhost:8000/api/status
curl https://<your-render-url>/api/status
```

Next steps I can do for you
- Create a small `render.yaml` or GitHub Actions workflow to auto-deploy on push.
- Tighten CORS in `app.py` to only allow your Streamlit Cloud URL.
- Add a `Procfile` for Heroku if you prefer.

If you want, I'll now:
- Add a `Procfile` and `render.yaml`, and create a GitHub Actions workflow to build and push the image to a container registry (choose provider).
