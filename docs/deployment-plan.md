# Deployment plan

The restaurant finder ships as two free services from one git repository.

| Piece | Host | What runs |
| --- | --- | --- |
| Frontend | Vercel Hobby | The Next.js app in `frontend/` |
| Backend | Railway Free | The FastAPI process, `python -m app.main` |

Vercel serves the page. The browser calls Railway for `GET /api/meta` and `POST /api/recommendations`. Railway also keeps the HTML routes, but the public page is the Vercel app.

Deploy Railway first. Its public URL has to exist before the Vercel build, because `NEXT_PUBLIC_API_URL` is baked into the frontend at build time.

## Limits that shape this plan

Railway Free is $0 and needs no card. It includes $1 of usage each month, one project, up to 0.5 GB RAM and 1 vCPU per service, a 4 GB image, and one `*.up.railway.app` domain. A service sleeps after about 5 to 10 minutes without outbound traffic and wakes on the next request. When the $1 is spent, the service stops until the next month. A new account also gets a 30-day trial with a one-time $5 credit. Details: [Railway Free plan](https://docs.railway.com/pricing/free-plan).

Vercel Hobby is $0. The Next.js app fits it. Set the project root to `frontend`. Details: [Vercel Hobby](https://vercel.com/docs/plans/hobby).

The running API loads `data/catalog.sqlite` once, at startup, from the process working directory (`CATALOG_PATH` in `app/catalog.py`). The file is about 12.8 MB and holds 12,494 restaurants. `data/` is gitignored today, so a GitHub build cannot see it. The process exits with `catalog not found` when the file is missing. This plan tracks that one sqlite file and still keeps `.env` out of git.

`requirements.txt` also installs `datasets` and `pytest`. Those are for ingest and tests. The Railway image installs only the four packages the server imports, so the process stays inside the 0.5 GB RAM cap.

The ranker calls Groq only when `LLM_BASE_URL`, `LLM_API_KEY`, and `LLM_MODEL` are all set. Leave them empty on Railway. Searches then use the rating-and-votes list and still return cards.

## Before either host

Do this on a branch, then push. Both hosts deploy from that branch.

### 1. Track the catalog, and nothing secret

In `.gitignore`, replace the `data/` line with:

```
data/*
!data/catalog.sqlite
```

Confirm `.env` is still ignored. Commit `data/catalog.sqlite`. Do not commit `.env`. The Groq key stays in the local file only.

Add `frontend/.gitignore`:

```
node_modules
.next
out
```

### 2. Listen on Railway's port

A local run stays on `127.0.0.1:8000`. When Railway sets `PORT`, `app/main.py` listens on `0.0.0.0` and that port. The image start command is:

```
python -m app.main --host 0.0.0.0 --port ${PORT:-8080}
```

These log lines mean the process started. They are not a crash:

```
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8080
```

The public URL fails when the domain's target port is still 8000. Set it to the port in that log, which is 8080. The process also listens on 8000 when `PORT` is a different port, so a domain left on 8000 still reaches the API.

### 3. Allow the Vercel origin

`CORSMiddleware` in `app/main.py` currently allows only `http://127.0.0.1:3000` and `http://localhost:3000`. A page on `https://….vercel.app` cannot call the API until the Railway origin list includes that page.

Read a comma-separated `CORS_ORIGINS` environment variable. Keep the two local origins so `npm run dev` still works. Add `allow_origin_regex` for `https://.*\.vercel\.app` so production and preview URLs are accepted. Methods stay `GET` and `POST`. The allowed header stays `Content-Type`.

### 4. Add the Railway image files

`requirements-serve.txt` at the repository root:

```
fastapi==0.163.2
uvicorn==0.54.0
pydantic==2.14.3
httpx==0.28.1
```

`Dockerfile` at the repository root:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements-serve.txt .
RUN pip install --no-cache-dir -r requirements-serve.txt

COPY app ./app
COPY data/catalog.sqlite ./data/catalog.sqlite

CMD ["/bin/sh", "-c", "exec python -m app.main --host 0.0.0.0 --port ${PORT:-8080}"]
```

Do not set `ENV PORT=8000` or `EXPOSE 8000`. Railway injects `PORT` and uses it as the domain target. An exposed 8000 sends visitors to a port where nothing is listening.

`.dockerignore`:

```
.venv
.git
.env
frontend
tests
docs
stitch_bangalore_restaurant_finder_ui
**/__pycache__
.pytest_cache
```

Leave `data/catalog.sqlite` out of that list so the image copy succeeds.

## Railway

1. Create a project from the GitHub repository. One service. Root directory is the repository root, where the `Dockerfile` sits.
2. Railway detects the `Dockerfile` and builds it. `railway.toml` sets the health check path to `/health`.
3. Generate a public domain. It looks like `https://<service>.up.railway.app`. No trailing slash. In **Settings → Networking**, set that domain's target port to the port in the Uvicorn log. On Railway that is **8080**, not 8000.
4. Variables, only if you later want model ranking:
   - `LLM_BASE_URL` = `https://api.groq.com/openai/v1`
   - `LLM_API_KEY` = the Groq key, typed into Railway's variable UI
   - `LLM_MODEL` = the model id
5. Leave those three unset for the first deploy.
6. Open `https://<service>.up.railway.app/health`. The body is `{"status":"ok"}`.
7. Open `https://<service>.up.railway.app/api/meta`. The JSON includes `locations` (Bangalore and Bengaluru first) and `costP33` / `costP66`.

A failed boot that logs `catalog not found` means the sqlite file was not in the build. Check that the git commit contains `data/catalog.sqlite` and that `.dockerignore` does not exclude it.

The first request after a sleep reloads the catalog into memory. Give `/health` about half a minute on that wake.

## Vercel

1. Import the same GitHub repository. Framework preset is Next.js.
2. Set **Root Directory** to `frontend`. Build command `npm run build`. Install command `npm install`. Leave the output directory on the Next.js default.
3. Environment variable, for Production and Preview:

   `NEXT_PUBLIC_API_URL` = `https://<service>.up.railway.app`

   No trailing slash. `frontend/src/lib/api.ts` joins this value with `/api/meta` and `/api/recommendations`. An empty value falls back to `http://127.0.0.1:8000`, which a visitor's browser cannot reach.
4. Deploy. Changing `NEXT_PUBLIC_API_URL` later requires a new Vercel build. A restart is not enough.
5. Copy the production URL, `https://<project>.vercel.app`.

## Join the two

1. On Railway, set `CORS_ORIGINS` to the Vercel production URL.
2. Redeploy the Railway service so the process picks up the variable.
3. Reload the Vercel page. The location list should show Bangalore, Bengaluru, and the neighborhoods. Budget text should show the catalog edges (low at or under ₹300, medium through the stored upper edge, high above that).

## Checks

Run these against the public URLs.

| Check | Expect |
| --- | --- |
| `GET /health` | `200` and `{"status":"ok"}` |
| `GET /api/meta` from the Vercel origin | `200`, locations, budget edges |
| Bangalore, Medium, cuisine Biryani, minimum rating 4 | Five cards, each with a name, cuisines, rating, cost for two, neighborhood, online order, table booking, and an explanation |
| Location left blank | The page lists the validation errors and shows no cards |
| A neighborhood, budget, cuisine, and rating that match nothing | “No restaurants match”, with the four filters echoed |
| Browser devtools on the Vercel page | `POST /api/recommendations` is `200` or `400`, and there is no CORS error |

Local `python -m pytest -q` stays on your machine. Do not run the test suite on Railway.

## Stay out of the hosts

- `.env` and `LLM_API_KEY`
- `frontend/node_modules` and `frontend/.next`
- The Hugging Face download and `python -m app.ingest` (the catalog is already built)
- The Stitch export under `stitch_bangalore_restaurant_finder_ui`

## Done when

- `https://<service>.up.railway.app/health` returns `{"status":"ok"}`.
- `https://<service>.up.railway.app/api/meta` returns the location list.
- The Vercel page loads that list and a Bangalore / Medium / Biryani / 4 search returns cards.
- The Groq key is only in Railway's variable UI, or it is unset and the fallback notice is visible.
