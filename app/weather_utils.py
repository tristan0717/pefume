import os
import requests
from dotenv import load_dotenv

load_dotenv()
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")

def get_weather_data(lat, lon):
    """OpenWeatherMap 원본 JSON 반환"""
    url = (
        f"https://api.openweathermap.org/data/2.5/weather"
        f"?lat={lat}&lon={lon}&appid={WEATHER_API_KEY}"
        f"&lang=kr&units=metric"
    )
    resp = requests.get(url)
    return resp.json() if resp.status_code == 200 else None

def get_weather(lat, lon):
    """클라이언트용 문자열 포맷 반환"""
    data = get_weather_data(lat, lon)
    if not data:
        return "날씨 정보를 가져올 수 없습니다."
    name = data["name"]
    desc = data["weather"][0]["description"]
    temp = data["main"]["temp"]
    return f"{name}의 현재 날씨는 {desc}이며, 기온은 {temp}°C 입니다."
