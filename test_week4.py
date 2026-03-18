"""
test_week4.py — Quick diagnostic tests for Week 4 agents.
Run this if something is not working.
"""
import os
from dotenv import load_dotenv
load_dotenv()

print("=" * 60)
print("Week 4 Diagnostic Tests")
print("=" * 60)

# Test 1: API keys
print("\n1. API Keys:")
for key in ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY"]:
    val = os.getenv(key)
    status = "SET" if val and not val.startswith("your-") else "MISSING"
    print(f"   {key}: {status}")

# Test 2: LLM connections
print("\n2. LLM Connections:")
try:
    from langchain_openai import ChatOpenAI
    llm = ChatOpenAI(model="gpt-4o-mini")
    r = llm.invoke("Say OK")
    print(f"   GPT-4o-mini: OK ({r.content[:20]})")
except Exception as e:
    print(f"   GPT-4o-mini: FAILED ({e})")

try:
    from langchain_anthropic import ChatAnthropic
    llm = ChatAnthropic(model="claude-sonnet-4-6", max_tokens=50)
    r = llm.invoke("Say OK")
    print(f"   Claude Sonnet: OK ({r.content[:20]})")
except Exceptn as e:
    print(f"   Claude Sonnet: FAILED ({e})")

try:
    from langchain_google_genai import ChatGoogleGenerativeAI
    llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash")
    r = llm.invoke("Say OK")
    print(f"   Gemini Flash: OK ({r.content[:20]})")
except Exception as e:
    print(f"   Gemini Flash: FAILED ({e})")

# Test 3: Model files
print("\n3. ML Model:")
model_path = os.path.join("models", "model.json")
meta_path = os.path.join("models", "metadata.json")
print(f"   model.json: {'EXISTS' if os.path.exists(model_path) else 'MISSING'}")
print(f"   metadata.json: {'EXISTS' if os.path.exists(meta_path) else 'MISSING'}")

# Test 4: Database
print("\n4. Database:")
try:
    from tools.database import get_database_status
    status = get_database_status()
    for table, count in status.items():
        print(f"   {table}: {count}")
except Exception as e:
    print(f"   FAILED: {e}")

# Test 5: Tool imports
print("\n5. Tool Imports:")
for module in ["tools.ml_model", "tools.report_tools", "tools.database", "tools.cricket_api"]:
    try:
        __import__(module)
        print(f"   {module}: OK")
    except Exception as e:
        print(f"   {module}: FAILED ({e})")

# Test 6: Agent imports
print("\n6. Agent Imports:")
for module in ["agents.explainer_agent", "agents.report_agent", "agents.orchestrator", "agents.graph"]:
    try:
        __import__(module)
        print(f"   {module}: OK")
    except Exception as e:
        print(f"   {module}: FAILED ({e})")

print("\n" + "=" * 60)
print("Fix any MISSING or FAILED items before proceeding.")
print("=" * 60)
