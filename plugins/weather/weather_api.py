"""
Weather API handler for fetching weather data from weatherapi.com
"""

import requests
import logging

logger = logging.getLogger("weather_api")

class WeatherAPI:
    def __init__(self, api_key, provider="weatherapi"):
        self.api_key = api_key
        self.provider = provider
        self.base_url = "http://api.weatherapi.com/v1/current.json"
    
    def get_weather(self, location):
        """
        Fetch current weather for a given location.
        
        Args:
            location (str): City name or location query
            
        Returns:
            dict: Weather data or error message
        """
        if not self.api_key:
            return {"error": "API key not configured"}
        
        try:
            url = f"{self.base_url}?key={self.api_key}&q={location}&aqi=no"
            response = requests.get(url, timeout=10)
            data = response.json()
            
            if response.status_code == 200:
                location_name = data["location"]["name"]
                country = data["location"]["country"]
                temp_c = data["current"]["temp_c"]
                temp_f = data["current"]["temp_f"]
                condition = data["current"]["condition"]["text"]
                humidity = data["current"]["humidity"]
                wind_kph = data["current"]["wind_kph"]
                
                return {
                    "success": True,
                    "location": location_name,
                    "country": country,
                    "temp_c": temp_c,
                    "temp_f": temp_f,
                    "condition": condition,
                    "humidity": humidity,
                    "wind_kph": wind_kph
                }
            else:
                error_msg = data.get("error", {}).get("message", "Unknown error")
                logger.error(f"Weather API error: {error_msg}")
                return {"success": False, "error": error_msg}
                
        except requests.exceptions.Timeout:
            logger.error("Weather API request timed out")
            return {"success": False, "error": "Request timed out"}
        except requests.exceptions.RequestException as e:
            logger.error(f"Weather API request failed: {e}")
            return {"success": False, "error": f"Request failed: {e}"}
        except Exception as e:
            logger.error(f"Unexpected error in weather API: {e}")
            return {"success": False, "error": f"Unexpected error: {e}"}
    
    def format_weather_response(self, weather_data):
        """
        Format weather data into a user-friendly message.
        
        Args:
            weather_data (dict): Weather data from API
            
        Returns:
            str: Formatted weather message
        """
        if not weather_data.get("success"):
            return f"⚠️ Weather data unavailable: {weather_data.get('error', 'Unknown error')}"
        
        return (
            f"🌤 *Weather in {weather_data['location']}, {weather_data['country']}*\n"
            f"🌡 Temperature: {weather_data['temp_c']}°C ({weather_data['temp_f']}°F)\n"
            f"☁️ Condition: {weather_data['condition']}\n"
            f"💧 Humidity: {weather_data['humidity']}%\n"
            f"💨 Wind: {weather_data['wind_kph']} km/h"
        )
