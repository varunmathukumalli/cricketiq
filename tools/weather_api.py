"""
weather_api.py — Open-Meteo weather data tool.

Fetches weather data for cricket venues using the free Open-Meteo API.
No API key required.

The Weather Agent will call these functions as tools.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import requests
from datetime import datetime, timedelta
from tools.database import query_database


def get_venue_coordinates(venue_name: str) -> dict | None:
    """Look up latitude/longitude for a venue from our database.

    Args:
        venue_name: The venue name (e.g., 'Wankhede Stadium')

    Returns:
        Dict with 'latitude', 'longitude', 'city', 'country' or None
    """
    # Try exact match first
    results = query_database(
        "SELECT name, city, country, latitude, longitude FROM venues WHERE name = %s",
        (venue_name,)
    )

    # Try fuzzy match if exact fails
    # APIs often send "Venue Name, City" — try matching both directions
    if not results:
        results = query_database(
            "SELECT name, city, country, latitude, longitude FROM venues WHERE name ILIKE %s",
            (f"%{venue_name}%",)
        )

    # Try: is the DB venue name contained IN the API string?
    # e.g., DB has "St George's Park", API sends "St George's Park, Gqeberha"
    if not results:
        results = query_database(
            "SELECT name, city, country, latitude, longitude FROM venues WHERE %s ILIKE '%%' || name || '%%'",
            (venue_name,)
        )

    # Last resort: try just the part before the comma
    if not results and "," in venue_name:
        venue_prefix = venue_name.split(",")[0].strip()
        results = query_database(
            "SELECT name, city, country, latitude, longitude FROM venues WHERE name ILIKE %s",
            (f"%{venue_prefix}%",)
        )

    if results:
        row = results[0]
        return {
            "venue": row["name"],
            "city": row["city"],
            "country": row["country"],
            "latitude": float(row["latitude"]),
            "longitude": float(row["longitude"]),
        }
    return None


def fetch_weather_for_venue(
    venue_name: str,
    date: str | None = None,
) -> dict:
    """Fetch weather data for a cricket venue on a specific date.

    Uses Open-Meteo API (free, no key needed).

    Args:
        venue_name: Name of the cricket venue
        date: Date string in YYYY-MM-DD format. Defaults to today.

    Returns:
        Dict with weather data and metadata, or error info.
    """
    coords = get_venue_coordinates(venue_name)
    if not coords:
        return {
            "error": f"Venue '{venue_name}' not found in database. "
                     f"Add it to the venues table with coordinates first.",
            "venue": venue_name,
        }

    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    # Determine if this is historical or forecast
    target_date = datetime.strptime(date, "%Y-%m-%d").date()
    today = datetime.now().date()

    if target_date <= today:
        # Historical data
        url = "https://archive-api.open-meteo.com/v1/archive"
        params = {
            "latitude": coords["latitude"],
            "longitude": coords["longitude"],
            "start_date": date,
            "end_date": date,
            "hourly": "temperature_2m,relative_humidity_2m,dew_point_2m,wind_speed_10m,precipitation,weather_code",
            "timezone": "auto",
        }
    else:
        # Forecast data (up to 16 days ahead)
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": coords["latitude"],
            "longitude": coords["longitude"],
            "start_date": date,
            "end_date": date,
            "hourly": "temperature_2m,relative_humidity_2m,dew_point_2m,wind_speed_10m,precipitation,weather_code",
            "timezone": "auto",
        }

    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
        return {"error": f"API request failed: {str(e)}", "venue": venue_name}

    hourly = data.get("hourly", {})
    if not hourly or not hourly.get("time"):
        return {"error": "No hourly data returned", "venue": venue_name}

    # Cricket matches run from morning to late night (day/night, IPL, BBL, etc.).
    # Cover 8 AM to 2 AM next day to account for rain delays and late finishes.
    # Indices 8-23 cover the current day; hours 0-1 would need next day's data,
    # so we use 8-23 (18 hours) which covers the vast majority of play.
    match_hours = range(8, 24)  # 8 AM to midnight
    temps = hourly.get("temperature_2m", [])
    humidities = hourly.get("relative_humidity_2m", [])
    dew_points = hourly.get("dew_point_2m", [])
    wind_speeds = hourly.get("wind_speed_10m", [])
    precips = hourly.get("precipitation", [])
    weather_codes = hourly.get("weather_code", [])

    def avg_for_hours(data_list, hours):
        values = [data_list[h] for h in hours if h < len(data_list) and data_list[h] is not None]
        return round(sum(values) / len(values), 1) if values else None

    def max_for_hours(data_list, hours):
        values = [data_list[h] for h in hours if h < len(data_list) and data_list[h] is not None]
        return max(values) if values else None

    # Most common weather code during match hours
    match_codes = [weather_codes[h] for h in match_hours if h < len(weather_codes)]
    most_common_code = max(set(match_codes), key=match_codes.count) if match_codes else None

    return {
        "venue": coords["venue"],
        "city": coords["city"],
        "country": coords["country"],
        "date": date,
        "latitude": coords["latitude"],
        "longitude": coords["longitude"],
        "match_hours_avg": {
            "temperature_c": avg_for_hours(temps, match_hours),
            "humidity_pct": avg_for_hours(humidities, match_hours),
            "dew_point_c": avg_for_hours(dew_points, match_hours),
            "wind_speed_kmh": avg_for_hours(wind_speeds, match_hours),
            "precipitation_mm": round(sum(
                precips[h] for h in match_hours
                if h < len(precips) and precips[h] is not None
            ), 1),
            "weather_code": most_common_code,
        },
        "dew_risk": {
            "dew_point_6pm": dew_points[18] if len(dew_points) > 18 else None,
            "humidity_6pm": humidities[18] if len(humidities) > 18 else None,
            "humidity_8pm": humidities[20] if len(humidities) > 20 else None,
            "dew_point_10pm": dew_points[22] if len(dew_points) > 22 else None,
            "humidity_10pm": humidities[22] if len(humidities) > 22 else None,
            "humidity_midnight": humidities[23] if len(humidities) > 23 else None,
        },
        "full_hourly": {
            "times": hourly.get("time", []),
            "temperatures": temps,
            "humidities": humidities,
            "dew_points": dew_points,
            "wind_speeds": wind_speeds,
            "precipitation": precips,
        },
    }


def fetch_weather_for_match(match_id: str) -> dict:
    """Fetch weather for a match by looking up its venue and date.

    Args:
        match_id: The match ID from the matches table.

    Returns:
        Weather data dict or error dict.
    """
    matches = query_database(
        "SELECT venue, date FROM matches WHERE id = %s",
        (match_id,)
    )

    if not matches:
        return {"error": f"Match {match_id} not found in database."}

    match = matches[0]
    venue = match.get("venue")
    date = match.get("date")

    if not venue:
        return {"error": f"Match {match_id} has no venue recorded."}

    date_str = None
    if date:
        if isinstance(date, str):
            date_str = date[:10]
        else:
            date_str = date.strftime("%Y-%m-%d")

    return fetch_weather_for_venue(venue, date_str)


# WMO Weather Code descriptions (used by Open-Meteo)
WMO_CODES = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Foggy",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    71: "Slight snowfall",
    73: "Moderate snowfall",
    75: "Heavy snowfall",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


def describe_weather_code(code: int) -> str:
    """Convert a WMO weather code to a human-readable description."""
    return WMO_CODES.get(code, f"Unknown code ({code})")


# Test
if __name__ == "__main__":
    print("Testing weather API tool...")
    print()

    # Test with a known venue
    result = fetch_weather_for_venue("Wankhede Stadium")
    if "error" in result:
        print(f"Error: {result['error']}")
    else:
        avg = result["match_hours_avg"]
        print(f"Venue: {result['venue']} ({result['city']}, {result['country']})")
        print(f"Date:  {result['date']}")
        print(f"Match-hours average:")
        print(f"  Temperature: {avg['temperature_c']}C")
        print(f"  Humidity:    {avg['humidity_pct']}%")
        print(f"  Dew point:   {avg['dew_point_c']}C")
        print(f"  Wind speed:  {avg['wind_speed_kmh']} km/h")
        print(f"  Rain total:  {avg['precipitation_mm']} mm")
        code = avg.get("weather_code")
        if code is not None:
            print(f"  Conditions:  {describe_weather_code(code)}")
        print(f"\nDew risk (evening/night):")
        dew = result["dew_risk"]
        print(f"  Dew point at 6 PM:  {dew['dew_point_6pm']}C")
        print(f"  Humidity at 6 PM:   {dew['humidity_6pm']}%")
        print(f"  Humidity at 8 PM:   {dew['humidity_8pm']}%")
        print(f"  Dew point at 10 PM: {dew['dew_point_10pm']}C")
        print(f"  Humidity at 10 PM:  {dew['humidity_10pm']}%")
        print(f"  Humidity midnight:  {dew['humidity_midnight']}%")

    print("\nDone!")
