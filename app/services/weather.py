import httpx

from app.config import settings

OPENWEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"


class WeatherError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


async def fetch_weather(city: str) -> dict:
    if not settings.openweather_api_key:
        raise WeatherError("OpenWeatherMap API key is not configured.")

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(
            OPENWEATHER_URL,
            params={
                "q": city,
                "units": "imperial",
                "appid": settings.openweather_api_key,
            },
        )

    data = response.json()

    if response.status_code != 200:
        api_message = data.get("message", "City not found.")
        raise WeatherError(api_message)

    return data


def build_weather_response(
    weather: dict,
    threshold_f: float | None = None,
    sms_sent: bool = False,
    email_sent: bool = False,
) -> dict:
    threshold = threshold_f if threshold_f is not None else settings.cold_threshold_f
    temp = weather["main"]["temp"]
    description = weather["weather"][0]["description"]
    city_name = weather["name"]
    is_cold = temp < threshold

    if is_cold:
        if sms_sent and email_sent:
            message = (
                f"It's {round(temp)}°F and {description} in {city_name}. "
                "It's cold — I've texted and emailed you a coat reminder."
            )
        elif sms_sent:
            message = (
                f"It's {round(temp)}°F and {description} in {city_name}. "
                "It's cold — I've texted you a coat reminder."
            )
        elif email_sent:
            message = (
                f"It's {round(temp)}°F and {description} in {city_name}. "
                "It's cold — I've emailed you a coat reminder."
            )
        else:
            message = (
                f"It's {round(temp)}°F and {description} in {city_name}. "
                "It's cold — bring a coat!"
            )
    else:
        message = (
            f"It's {round(temp)}°F and {description} in {city_name}. "
            "No coat needed today!"
        )

    return {
        "temperature_f": temp,
        "description": description,
        "city": city_name,
        "is_cold": is_cold,
        "message": message,
    }


def build_sms_message(weather: dict) -> str:
    city_name = weather["name"]
    temp = weather["main"]["temp"]
    return f"Today's temperature in {city_name} is {round(temp)}°F.\n\nBring a coat."
