"""Quick test to verify your setup is working."""
import requests
import psycopg2
from dotenv import load_dotenv
import os

load_dotenv()

# Test 1: requests library works
print("1. Testing requests library...")
response = requests.get("https://httpbin.org/get")
print(f"   HTTP status: {response.status_code} (should be 200)")

# Test 2: database connection works
print("2. Testing database connection...")
conn = psycopg2.connect(os.getenv("DATABASE_URL"))
cur = conn.cursor()
cur.execute("SELECT version();")
version = cur.fetchone()
print(f"   Connected to: {version[0][:30]}...")
cur.close()
conn.close()

# Test 3: .env file loaded
print("3. Testing .env file...")
api_key = os.getenv("CRICKET_API_KEY")
print(f"   CRICKET_API_KEY loaded: {'Yes' if api_key else 'No (set it on Day 2)'}")

print("\nAll checks passed! You're ready for Day 2.")
