import httpx
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime

WEATHER_CODES = {
    0: {"description": 'Clear sky', "description_bn": 'পরিষ্কার আকাশ', "emoji": '☀️'},
    1: {"description": 'Mainly clear', "description_bn": 'অধিকাংশ পরিষ্কার', "emoji": '🌤️'},
    2: {"description": 'Partly cloudy', "description_bn": 'আংশিক মেঘলা', "emoji": '⛅'},
    3: {"description": 'Overcast', "description_bn": 'মেঘাচ্ছন্ন', "emoji": '☁️'},
    45: {"description": 'Fog', "description_bn": 'কুয়াশা', "emoji": '🌫️'},
    48: {"description": 'Dense fog', "description_bn": 'ঘন কুয়াশা', "emoji": '🌫️'},
    51: {"description": 'Light drizzle', "description_bn": 'হালকা গুঁড়ি বৃষ্টি', "emoji": '🌧️'},
    53: {"description": 'Moderate drizzle', "description_bn": 'মাঝারি গুঁড়ি বৃষ্টি', "emoji": '🌧️'},
    55: {"description": 'Dense drizzle', "description_bn": 'ঘন গুঁড়ি বৃষ্টি', "emoji": '🌧️'},
    61: {"description": 'Slight rain', "description_bn": 'হালকা বৃষ্টি', "emoji": '🌧️'},
    63: {"description": 'Moderate rain', "description_bn": 'মাঝারি বৃষ্টি', "emoji": '🌧️'},
    65: {"description": 'Heavy rain', "description_bn": 'ভারী বৃষ্টি', "emoji": '🌧️'},
    80: {"description": 'Slight rain showers', "description_bn": 'হালকা বৃষ্টি', "emoji": '🌦️'},
    81: {"description": 'Moderate rain showers', "description_bn": 'মাঝারি বৃষ্টি', "emoji": '🌦️'},
    82: {"description": 'Violent rain showers', "description_bn": 'প্রচণ্ড বৃষ্টি', "emoji": '⛈️'},
    95: {"description": 'Thunderstorm', "description_bn": 'বজ্রবৃষ্টি', "emoji": '⛈️'},
    96: {"description": 'Thunderstorm with hail', "description_bn": 'শিলাবৃষ্টিসহ বজ্রপাত', "emoji": '⛈️'},
    99: {"description": 'Thunderstorm with heavy hail', "description_bn": 'ভারী শিলাবৃষ্টিসহ বজ্রপাত', "emoji": '⛈️'},
}

WEATHER_COUNTRIES = [
    {
        "code": 'BD',
        "name": 'Bangladesh',
        "name_bn": 'বাংলাদেশ',
        "flag": '🇧🇩',
        "cities": [
            {"name": 'Dhaka', "name_bn": 'ঢাকা', "lat": 23.8103, "lon": 90.4125, "is_capital": True},
            {"name": 'Chittagong', "name_bn": 'চট্টগ্রাম', "lat": 22.3569, "lon": 91.7832},
            {"name": 'Sylhet', "name_bn": 'সিলেট', "lat": 24.8949, "lon": 91.8687},
            {"name": 'Rajshahi', "name_bn": 'রাজশাহী', "lat": 24.3745, "lon": 88.6042},
            {"name": 'Khulna', "name_bn": 'খুলনা', "lat": 22.8456, "lon": 89.5403},
            {"name": 'Barishal', "name_bn": 'বরিশাল', "lat": 22.7010, "lon": 90.3535},
            {"name": 'Rangpur', "name_bn": 'রংপুর', "lat": 25.7439, "lon": 89.2752},
            {"name": 'Mymensingh', "name_bn": 'ময়মনসিংহ', "lat": 24.7471, "lon": 90.4203},
            {"name": 'Sreemangal', "name_bn": 'শ্রীমঙ্গল', "lat": 24.3065, "lon": 91.7296},
            {"name": 'Tetulia', "name_bn": 'তেঁতুলিয়া', "lat": 26.4952, "lon": 88.3512},
            {"name": 'Cox\'s Bazar', "name_bn": "কক্সবাজার", "lat": 21.4272, "lon": 92.0058},
        ]
    }
]

class WeatherService:
    @staticmethod
    async def fetch_weather(lat: float, lon: float, location_name: str = "Unknown") -> Dict:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m,is_day&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,weather_code,sunrise,sunset&timezone=auto"
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            data = response.json()
            
            if "error" in data:
                raise Exception(data.get("reason", "Open-Meteo API error"))
            
            current = data["current"]
            daily = data["daily"]
            
            code_info = WEATHER_CODES.get(current["weather_code"], {"description": "Unknown", "description_bn": "অজানা", "emoji": "❓"})
            
            return {
                "location": {"name": location_name, "lat": lat, "lon": lon},
                "current": {
                    "temperature": round(current["temperature_2m"]),
                    "feels_like": round(current["apparent_temperature"]),
                    "humidity": current["relative_humidity_2m"],
                    "wind_speed": round(current["wind_speed_10m"]),
                    "weather_code": current["weather_code"],
                    "description": code_info["description"],
                    "description_bn": code_info["description_bn"],
                    "emoji": code_info["emoji"],
                    "is_day": current["is_day"] == 1
                },
                "daily": [
                    {
                        "date": daily["time"][i],
                        "temp_max": round(daily["temperature_2m_max"][i]),
                        "temp_min": round(daily["temperature_2m_min"][i]),
                        "precipitation": daily["precipitation_sum"][i],
                        "weather_code": daily["weather_code"][i],
                        "sunrise": daily["sunrise"][i] if "sunrise" in daily else None,
                        "sunset": daily["sunset"][i] if "sunset" in daily else None
                    } for i in range(len(daily["time"]))
                ]
            }

    @staticmethod
    def detect_alerts(weather: Dict) -> List[Dict]:
        alerts = []
        current = weather["current"]
        daily = weather["daily"]
        
        # Extreme Heat
        if current["temperature"] >= 40:
            alerts.append({"type": "extreme_heat", "severity": "critical", "viral_potential": 9, "title_bn": f"🔥 চরম তাপপ্রবাহ সতর্কতা: {current['temperature']}°C!"})
        elif current["temperature"] >= 38:
            alerts.append({"type": "extreme_heat", "severity": "warning", "viral_potential": 7, "title_bn": f"⚠️ তাপপ্রবাহ সতর্কতা: {current['temperature']}°C"})
            
        # Extreme Cold
        if current["temperature"] <= 5:
            alerts.append({"type": "extreme_cold", "severity": "critical", "viral_potential": 9, "title_bn": f"❄️ শৈত্যপ্রবাহ সতর্কতা: {current['temperature']}°C!"})
        elif current["temperature"] <= 10:
            alerts.append({"type": "extreme_cold", "severity": "warning", "viral_potential": 6, "title_bn": f"🧊 শীতল আবহাওয়া: {current['temperature']}°C"})
            
        # Heavy Rain / Storm
        if current["weather_code"] in [82, 95, 96, 99]:
            alerts.append({"type": "storm", "severity": "critical", "viral_potential": 10, "title_bn": "⛈️ ঝড় সতর্কতা! বজ্রবৃষ্টি চলছে"})
        elif current["weather_code"] == 65:
            alerts.append({"type": "heavy_rain", "severity": "warning", "viral_potential": 7, "title_bn": "🌧️ ভারী বৃষ্টি সতর্কতা"})
            
        return sorted(alerts, key=lambda x: x["viral_potential"], reverse=True)

    @classmethod
    async def fetch_country_weather(cls, country_code: str) -> List[Dict]:
        country = next((c for c in WEATHER_COUNTRIES if c["code"] == country_code), None)
        if not country: return []
        
        results = []
        for city in country["cities"]:
            try:
                w = await cls.fetch_weather(city["lat"], city["lon"], city["name_bn"])
                w["alerts"] = cls.detect_alerts(w)
                results.append(w)
            except Exception as e:
                print(f"Failed to fetch weather for {city['name']}: {e}")
                
        return results

    @classmethod
    async def generate_divisional_weather_table(cls, country_code: str) -> str:
        all_weather = await cls.fetch_country_weather(country_code)
        if not all_weather: return "আবহাওয়া তথ্য পাওয়া যায়নি।"
        
        # Filter to divisions (simplifying for now to top cities)
        divisions = all_weather[:8] 
        date_str = datetime.now().strftime("%d %B") # Needs conversion to BN for full parity
        
        post = f"আসুন এক নজরে দেখে নেই দেশের বিভাগীয় শহরের সম্ভাব্য সর্বোচ্চ ও সর্বনিম্ন তাপমাত্রা।\nসূত্র : অটোমেশন\n\n"
        post += f"বিভাগের নাম        সর্বোচ্চ       সর্বনিম্ন\n"
        post += f"--------------------------------------\n"
        
        for w in divisions:
            name = w["location"]["name"]
            max_t = f"+{w['daily'][0]['temp_max']}°"
            min_t = f"+{w['daily'][0]['temp_min']}°"
            post += f"{name.ljust(15)} {max_t.center(10)} {min_t.center(10)}\n"
            
        post += f"\nআপডেট : {datetime.now().strftime('%I:%M %p')}\n"
        return post

    @classmethod
    async def generate_flash_update(cls, country_code: str) -> str:
        all_weather = await cls.fetch_country_weather(country_code)
        if not all_weather: return ""
        
        max_w = max(all_weather, key=lambda x: x["current"]["temperature"])
        min_w = min(all_weather, key=lambda x: x["current"]["temperature"])
        
        return f"আজকে দেশের সর্বোচ্চ তাপমাত্রা রেকর্ড করা হয়েছে {max_w['location']['name']} এ {max_w['current']['temperature']}° সেলসিয়াস এবং সর্বনিম্ন {min_w['location']['name']} এ {min_w['current']['temperature']}° সেলসিয়াস।\n\n#WeatherUpdate #Bangladesh"

    @classmethod
    async def get_viral_weather_update(cls, country_code: str) -> Optional[Dict]:
        all_weather = await cls.fetch_country_weather(country_code)
        best_w = None
        best_alert = None
        
        for w in all_weather:
            if w["alerts"]:
                top = w["alerts"][0]
                if not best_alert or top["viral_potential"] > best_alert["viral_potential"]:
                    best_alert = top
                    best_w = w
                    
        if best_w:
            return {"weather": best_w, "alert": best_alert}
        return None
