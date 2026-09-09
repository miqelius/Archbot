import httpx
from fastapi import APIRouter
import yfinance as yf

router = APIRouter()

@router.get("/history")
async def get_market_history():
    async with httpx.AsyncClient() as client:
        fx_resp = await client.get("https://api.frankfurter.app/latest?from=USD&to=EUR,GBP,GEL")
        fx_data = fx_resp.json()

    gold = yf.Ticker("GC=X")
    gold_hist = gold.history(period="7d")
    silver = yf.Ticker("SI=X")
    silver_hist = silver.history(period="7d")

    async with httpx.AsyncClient() as client:
        crypto_resp = await client.get("https://api.coingecko.com/api/v3/coins/bitcoin/market_chart?vs_currency=usd&days=7")
        crypto_data = crypto_resp.json()

    return {
        "fiat": fx_data.get("rates", {}),
        "gold": {str(date.date()): val for date, val in gold_hist["Close"].items()},
        "silver": {str(date.date()): val for date, val in silver_hist["Close"].items()},
        "crypto": crypto_data.get("prices", [])
    }
