import requests
import time

BASE_URL = "http://localhost:8000/api"

def test_pipeline():
    payload = {
        "text": "Test translation string",
        "target_language": "ka",
        "telegram_user_id": "123456789",
        "source_type": "text"
    }
    response = requests.post(f"{BASE_URL}/jobs", json=payload)
    print(f"Create Job Status: {response.status_code}")
    
    if response.status_code not in [200, 201]:
        print(f"Error response: {response.text}")
        return

    data = response.json()
    job_id = data.get("id") or data.get("job_id")
    print(f"Job ID received: {job_id}")

    for i in range(15):
        time.sleep(2)
        res = requests.get(f"{BASE_URL}/jobs/{job_id}/status")
        if res.status_code == 200:
            status_data = res.json()
            status = status_data.get("status")
            print(f"Attempt {i+1} - Job Status: {status}")
            if status in ["completed", "success", "failed", "FINISHED"]:
                print(f"Final result: {status_data}")
                break
        else:
            print(f"Failed to fetch status: {res.status_code} - {res.text}")

if __name__ == "__main__":
    test_pipeline()
