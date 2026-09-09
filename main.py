from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers.copilot import router as copilot_router
from routers.market import router as market_router
from routers.real_estate import router as real_estate_router
from routers.weather import router as weather_router
from routers.automation import router as automation_router

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

app.include_router(market_router, prefix="/api/market", tags=["Market"])
app.include_router(real_estate_router, prefix="/api/listings", tags=["Listings"])
app.include_router(weather_router, prefix="/api/weather", tags=["Weather"])
app.include_router(copilot_router, prefix="/api/copilot", tags=["Copilot"])
app.include_router(automation_router, prefix="/api/automation", tags=["Automation"])
