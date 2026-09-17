import json

def get_upcoming_ufc_event():
    upcoming_fights = [
        {"fighter_a": "Alex Pereira", "fighter_b": "Magomed Ankalaev", "sport": "UFC"},
        {"fighter_a": "Islam Makhachev", "fighter_b": "Arman Tsarukyan", "sport": "UFC"},
        {"fighter_a": "Ilia Topuria", "fighter_b": "Max Holloway", "sport": "UFC"},
        {"fighter_a": "Tom Aspinall", "fighter_b": "Curtis Blaydes", "sport": "UFC"}
    ]
    
    with open('ufc_fights.json', 'w', encoding='utf-8') as f:
        json.dump(upcoming_fights, f, ensure_ascii=False, indent=4)
        
    print(f"წარმატებით შენახდა {len(upcoming_fights)} ბრძოლა ufc_fights.json-ში!")
    return upcoming_fights

if __name__ == "__main__":
    get_upcoming_ufc_event()
