async def create_translation_job(
    user_id: str,
    username: Optional[str],
    source_type: SourceType,
    text: Optional[str] = None,
    file_bytes: Optional[bytes] = None,
    file_name: Optional[str] = None,
) -> str:
    """Create translation job via FastAPI endpoint"""
    
    # გაზრდილი ტაიმაუტი დიდი ფაილებისთვის
    async with httpx.AsyncClient(timeout=30.0) as client:
        url = f"{settings.api_host}:{settings.api_port}{settings.api_prefix}/jobs"
        
        # Form data-ს ველები
        data = {
            "telegram_user_id": user_id,
            "source_type": source_type.value,
            "source_language": "ka",
            "target_language": "en",
        }
        if username:
            data["telegram_username"] = username
            
        if text:
            data["text"] = text
            
        # ფაილის მომზადება გაგზავნისთვის
        files = None
        if file_bytes and file_name:
            files = {"file": (file_name, file_bytes)}
        
        response = await client.post(url, data=data, files=files)
        response.raise_for_status()
        
        result = response.json()
        return result["job_id"]
