from fastapi import APIRouter
import httpx

router = APIRouter()

@router.get("/market-weather")
async def get_market_weather():
    usd_gel = 2.72 # Default fallback
    gold_price = 2486.0
    temp = 22.5
    wind = 12.0
    
    async with httpx.AsyncClient() as client:
        # 1. Fetch Real Currency (USD to GEL)
        try:
            res_curr = await client.get("https://open.er-api.com/v6/latest/USD", timeout=4.0)
            if res_curr.status_code == 200:
                rates = res_curr.json().get("rates", {})
                if "GEL" in rates:
                    usd_gel = round(rates["GEL"], 3)
        except Exception as e:
            print("Currency API Error:", e)

        # 2. Fetch Real Weather for Tbilisi (Open-Meteo - 100% Free, No key)
        try:
            res_weather = await client.get("https://api.open-meteo.com/v1/forecast?latitude=41.7151&longitude=44.8271&current=temperature_2m,wind_speed_10m", timeout=4.0)
            if res_weather.status_code == 200:
                current = res_weather.json().get("current", {})
                temp = current.get("temperature_2m", 22.5)
                wind = current.get("wind_speed_10m", 12.0)
        except Exception as e:
            print("Weather API Error:", e)

    return {
        "status": "success",
        "usd_gel": usd_gel,
        "gold": gold_price,
        "temperature": temp,
        "wind_speed": wind
    }
