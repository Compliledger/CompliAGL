# Screenshots

This directory is reserved for real, captured screenshots of the CompliAGL
operator surfaces. **No screenshots are committed yet** — the images below are
required captures, not placeholders to be faked.

Please do **not** commit mocked or synthetic screenshots. Capture from a running
instance (`uvicorn app.main:app` + the Next.js frontend) so that every image
reflects real, current behavior.

## Required captures

| File | What to capture | Source surface |
|------|-----------------|----------------|
| `api-docs.png` | FastAPI interactive OpenAPI docs | `http://localhost:8000/docs` |
| `governance-decision.png` | A deterministic decision response (`POST /api/v1/decisions/decide`) | Backend API / SDK example |
| `aiproof-verify.png` | An AIProof local verification result (`POST /api/v1/aiproofs/{id}/verify`) | Backend API |
| `frontend-landing.png` | Frontend landing page | `CompliAgl-Frontend` (`npm run dev`) |

When you add an image here, reference it from the root `README.md` and update
this table with the commit that introduced it.
