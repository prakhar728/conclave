from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import router, register_skills

app = FastAPI(title="Conclave — NDAI Skills Service")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

register_skills()
app.include_router(router)
