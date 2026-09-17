import asyncio
import logging
import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN_HERE"
API_URL = "http://127.0.0.1:8000/api/predict"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "⚽ მოგესალმებით MatchMind AI-ში!\n\n"
        "მე ვათვლი მატჩების ზუსტ პროგნოზებს **Poisson-ის მათემატიკური განაწილებისა** და მრავალარხიანი აგენტების ანალიზით.\n\n"
        "გამოიყენე ბრძანება ამ ფორმატით პროგნოზისთვის:\n"
        "`/predict [მასპინძელი] [სტუმარი] [მასპინძლის xG] [სტუმრის xG]`\n\n"
        "მაგალითი:\n`/predict Arsenal Chelsea 1.85 1.10`"
    )

@dp.message(Command("predict"))
async def cmd_predict(message: types.Message):
    args = message.text.split()[1:]
    if len(args) < 4:
        await message.answer("⚠️ გთხოვ მიუთითო სწორი ფორმატი:\n`/predict Arsenal Chelsea 1.85 1.10`")
        return

    home, away, home_xg, away_xg = args[0], args[1], float(args[2]), float(args[3])

    payload = {
        "home_team": home,
        "away_team": away,
        "home_xg": home_xg,
        "away_xg": away_xg,
        "home_form": "W-W-D-W-L",
        "away_form": "L-D-W-W-L",
        "home_formation": "4-3-3",
        "away_formation": "4-4-2"
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(API_URL, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    probs = data["probabilities"]
                    
                    text = (
                        f"📊 **{data['teams']['home']} vs {data['teams']['away']}**\n\n"
                        f"🔹 **Poisson ალბათობები:**\n"
                        f"🏠 მოგება ({home}): **{probs['home_win_prob']}%**\n"
                        f"🤝 ფრე: **{probs['draw_prob']}%**\n"
                        f"✈️ მოგება ({away}): **{probs['away_win_prob']}%**\n\n"
                        f"⚽ დამატებითი ბაზრები:\n"
                        f"• Over 2.5 გოლი: **{probs['over_2.5_prob']}%**\n"
                        f"• ორივემ გაიტანა (BTTS): **{probs['btts_prob']}%**\n\n"
                        f"🧠 **AI აგენტების დასკვნა:**\n"
                        f"სისტემამ დაამუშავა xG, ფორმა და ტაქტიკა. პროგნოზი ეყრდნობა მკაცრ სტატისტიკას ყოველგვარი ზედმეტი გარანტიების გარეშე."
                    )
                    await message.answer(text, parse_mode="Markdown")
                else:
                    await message.answer("❌ სერვერთან კავშირის შეცდომაა.")
        except Exception as e:
            await message.answer(f"❌ შეცდომა: {str(e)}")

async def main():
    print(">>> Telegram ბოტი ჩაიწერა და იწყებს მუშაობას...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
