import httpx
from fastapi import APIRouter, HTTPException
import yfinance as yf

router = APIRouter()

@router.get("/history")
async def get_market_history():
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            fx_resp = await client.get("https://api.frankfurter.app/latest?from=USD&to=EUR,GBP,GEL")
            fx_data = fx_resp.json() if fx_resp.status_code == 200 else {}

            crypto_resp = await client.get("https://api.coingecko.com/api/v3/coins/bitcoin/market_chart?vs_currency=usd&days=7")
            crypto_data = crypto_resp.json() if crypto_resp.status_code == 200 else {}

        gold_prices = {}
        try:
            gold = yf.Ticker("GC=X")
            gold_hist = gold.history(period="7d")
            if not gold_hist.empty and "Close" in gold_hist.columns:
                gold_prices = {str(date.date()): float(val) for date, val in gold_hist["Close"].items()}
        except Exception as e:
            gold_prices = {"error": str(e)}

        silver_prices = {}
        try:
            silver = yf.Ticker("SI=X")
            silver_hist = silver.history(period="7d")
            if not silver_hist.empty and "Close" in silver_hist.columns:
                silver_prices = {str(date.date()): float(val) for date, val in silver_hist["Close"].items()}
        except Exception as e:
            silver_prices = {"error": str(e)}

        return {
            "fiat": fx_data.get("rates", {}),
            "gold": gold_prices,
            "silver": silver_prices,
            "crypto": crypto_data.get("prices", [])
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
