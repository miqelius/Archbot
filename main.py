from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import copilot, market, real_estate, weather, automation

app = FastAPI(title="Archbot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"status": "operational", "service": "Archbot API"}

app.include_router(market.router, prefix="/api/market", tags=["Market"])
app.include_router(real_estate.router, prefix="/api/listings", tags=["Listings"])
app.include_router(weather.router, prefix="/api/weather", tags=["Weather"])
app.include_router(copilot.router, prefix="/api/copilot", tags=["Copilot"])
app.include_router(automation.router, prefix="/api/automation", tags=["Automation"])
