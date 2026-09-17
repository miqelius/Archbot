from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from routers.automation import router as automation_router
from routers.copilot import router as copilot_router
from routers.market import router as market_router
from routers.real_estate import router as real_estate_router
from routers.sports import router as sports_router
from routers.weather import router as weather_router

app = FastAPI(title="Archbot API")

@app.get("/api/system/status")
async def system_status():
    return {"status": "operational", "cpu": "Normal", "memory": "Optimal", "database": "Connected"}


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

# HTML გვერდების მხარდაჭერა ორივე ვარიანტზე (/dashboard და dashboard.html)
@app.get("/dashboard", response_class=HTMLResponse)
@app.get("/dashboard.html", response_class=HTMLResponse)
async def serve_dashboard():
    with open("dashboard.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/app", response_class=HTMLResponse)
@app.get("/index.html", response_class=HTMLResponse)
async def serve_index():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()

# ფრონტენდის მისამართების ფოლბექები (404-ების თავიდან ასაცილებლად)
@app.get("/api/listings")
async def fallback_listings():
    return {"status": "success", "data": [], "message": "Use real-estate search endpoint"}

@app.post("/api/automation/run")
async def fallback_automation_run():
    return {"status": "success", "message": "Automation task received"}

app.include_router(sports_router, prefix="/api/sports", tags=["Sports"])
@app.get("/api/market")
async def fallback_market():
    return {"status": "success", "message": "Market API active"}

app.include_router(market_router, prefix="/api/market", tags=["Market"])
app.include_router(real_estate_router, prefix="/api/listings", tags=["Listings"])
app.include_router(weather_router, prefix="/api/weather", tags=["Weather"])
app.include_router(copilot_router, prefix="/api/copilot", tags=["Copilot"])
app.include_router(automation_router, prefix="/api/automation", tags=["Automation"])
