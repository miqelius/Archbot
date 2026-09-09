import requests
from bs4 import BeautifulSoup
from database import SessionLocal
from models import RealEstateListing

def scrape_and_save_listings(target_url: str):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        response = requests.get(target_url, headers=headers, timeout=10)
        if response.status_code != 200:
            return {"status": "error", "message": "Failed to fetch target page"}

        soup = BeautifulSoup(response.text, 'html.parser')
        db = SessionLocal()
        
        added_count = 0
        listings = soup.find_all("div", class_="listing-item")
        for item in listings:
            title_elem = item.find("h2")
            price_elem = item.find("span", class_="price")
            
            if title_elem and price_elem:
                title = title_elem.get_text(strip=True)
                price_str = price_elem.get_text(strip=True).replace("$", "").replace(",", "").strip()
                price = float(price_str) if price_str.replace('.', '', 1).isdigit() else 0.0
                
                exists = db.query(RealEstateListing).filter_by(title=title).first()
                if not exists:
                    new_listing = RealEstateListing(title=title, price=price)
                    db.add(new_listing)
                    added_count += 1
                    
        db.commit()
        db.close()
        return {"status": "success", "added_listings": added_count}
    except Exception as e:
        return {"status": "error", "details": str(e)}
