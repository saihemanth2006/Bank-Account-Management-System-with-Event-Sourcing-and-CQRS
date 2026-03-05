import os
from fastapi import FastAPI
import databases

from . import commands, projections

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@db:5432/postgres")
API_PORT = int(os.getenv("API_PORT", "8000"))

database = databases.Database(DATABASE_URL)

app = FastAPI(title="Bank ES/CQRS API")


@app.on_event("startup")
async def startup():
    try:
        await database.connect()
    except Exception:
        pass


@app.on_event("shutdown")
async def shutdown():
    try:
        await database.disconnect()
    except Exception:
        pass


@app.get("/health")
async def health():
    return {"status": "ok"}


# Mount command and query routers
app.include_router(commands.router, prefix="/api", tags=["commands"]) 
app.include_router(projections.router, prefix="/api", tags=["queries"]) 

