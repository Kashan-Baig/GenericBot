from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Load local .env before the API/flow modules are used.
load_dotenv()

from app.api.routes import router as api_router
from app.api.webhooks import router as webhooks_router
from app.flows.loader import load_flow


app = FastAPI(
    title="Configurable Chatbot Workflow Engine",
    description="Backend engine built on LangGraph to execute dynamic conversation flows.",
    version="1.0.0"
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# API ROUTES
# ============================================================

app.include_router(api_router)
app.include_router(webhooks_router)


# ============================================================
# STARTUP
# ============================================================

@app.on_event("startup")
async def startup_event():
    # Pre-cache demo_flow on startup
    load_flow("demo_flow")


# ============================================================
# ROOT
# ============================================================

@app.get("/")
async def root():
    return {
        "message": "Chatbot Workflow Engine API is running.",
        "docs": "/docs"
    }