# Deployment Instructions — SBI Sarathi MVP

This guide explains how to deploy the SBI Sarathi proactive assistant to production environments.

## 1. Backend Deployment (Railway or Render)

The Python FastAPI backend can be deployed using the provided `Dockerfile`.

### Option A: Railway (Recommended)

Railway offers extremely simple container-based deployment with automatic builds.

1. Install the Railway CLI or connect your GitHub repository directly at [railway.app](https://railway.app).
2. Create a new project on Railway.
3. Add a service from your GitHub repo.
4. Set the following environment variables:
   - `LLM_API_KEY`: Your OpenAI-compatible API key (optional, falls back to demo mode if blank)
   - `LLM_API_BASE_URL`: `https://api.openai.com/v1/chat/completions` (or other provider)
   - `LLM_MODEL`: Model name (e.g. `gpt-4o-mini`)
5. Railway will automatically detect the `Dockerfile`, build the container, expose port `8000`, and provide a public domain.

### Option B: Render

Render is another free/cheap hosting provider for Docker services.

1. Go to [dashboard.render.com](https://dashboard.render.com) and create a **Web Service**.
2. Connect your Git repository.
3. Select **Docker** as the runtime.
4. Set Environment Variables under the service configuration (same as above).
5. Set `PORT` variable to `8000`.
6. Click deploy. Render will build and deploy the container.

---

## 2. Frontend Deployment (Vercel)

The Next.js frontend is built for easy serverless deployment on Vercel.

1. Create a free account at [vercel.com](https://vercel.com).
2. Connect your GitHub repository.
3. Import the repository and select the `frontend` subdirectory as the root directory of the project.
   - Set **Framework Preset** to **Next.js**.
   - Set **Root Directory** to `frontend`.
4. Vercel will automatically configure the build commands (`npm run build`) and output directory.
5. Deploy! Vercel will provide a secure HTTPS URL for your single-page dashboard.

> [!NOTE]
> Ensure that your frontend points to the correct production backend URL. You can modify the `API_BASE` constant in [page.tsx](file:///d:/Projects/SBI/frontend/src/app/page.tsx#L6) or use an environment variable (`NEXT_PUBLIC_API_URL`) to dynamically route API requests.
