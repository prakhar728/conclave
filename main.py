from fastapi import FastAPI, Request
from fastapi.responses import Response
from api.routes import router, register_skills

app = FastAPI(title="Conclave — NDAI Skills Service")


@app.middleware("http")
async def cors_middleware(request: Request, call_next):
    if request.method == "OPTIONS":
        response = Response(status_code=200)
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "*"
        return response
    response = await call_next(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response

register_skills()
app.include_router(router)
