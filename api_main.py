from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers.automation import router as automation_router
from routers.copilot import router as copilot_router
from routers.market import router as market_router
from routers.real_estate import router as real_estate_router
from routers.sports import router as sports_router
from routers.weather import router as weather_router

# 1. ვქმნით FastAPI აპლიკაციას
app = FastAPI(title="Archbot API")

# 2. ვრთავთ CORS მიდლვერს
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 3. მთავარი მისამართი
@app.get("/")
async def root():
    return {"status": "operational", "service": "Archbot API"}


# 4. ვრთავთ ყველა როუტს
app.include_router(sports_router, prefix="/api/sports", tags=["Sports"])
app.include_router(market_router, prefix="/api/market", tags=["Market"])
app.include_router(real_estate_router, prefix="/api/listings", tags=["Listings"])
app.include_router(weather_router, prefix="/api/weather", tags=["Weather"])
app.include_router(copilot_router, prefix="/api/copilot", tags=["Copilot"])
app.include_router(
    automation_router, prefix="/api/automation", tags=["Automation"]
)
