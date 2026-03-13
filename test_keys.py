"""Test that all API keys are configured and working."""
from dotenv import load_dotenv
import os

load_dotenv()

keys = {
    "ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY"),
    "GOOGLE_API_KEY": os.getenv("GOOGLE_API_KEY"),
    "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
    "CRICKET_API_KEY": os.getenv("CRICKET_API_KEY"),
    "DATABASE_URL": os.getenv("DATABASE_URL"),
}

print("API Key Status:")
for name, value in keys.items():
    status = "SET" if value and not value.startswith("your-") else "MISSING"
    print(f"  {name}: {status}")

# Test each LLM
print("\nTesting LLMs...")

try:
    from langchain_google_genai import ChatGoogleGenerativeAI
    llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash")
    response = llm.invoke("Say 'hello' and nothing else.")
    print(f"  Gemini Flash: OK ({response.content[:30]}...)")
except Exception as e:
    print(f"  Gemini Flash: FAILED ({e})")

try:
    from langchain_openai import ChatOpenAI
    llm = ChatOpenAI(model="gpt-4o-mini")
    response = llm.invoke("Say 'hello' and nothing else.")
    print(f"  GPT-4o-mini:  OK ({response.content[:30]}...)")
except Exception as e:
    print(f"  GPT-4o-mini:  FAILED ({e})")

try:
    from langchain_anthropic import ChatAnthropic
    llm = ChatAnthropic(model="claude-sonnet-4-6")
    response = llm.invoke("Say 'hello' and nothing else.")
    print(f"  Claude Sonnet: OK ({response.content[:30]}...)")
except Exception as e:
    print(f"  Claude Sonnet: FAILED ({e})")

print("\nDone! Fix any MISSING or FAILED items before proceeding.")
