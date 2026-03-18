"""Quick test that the ML tools are properly decorated and callable by agents."""
from tools.ml_model import get_prediction, get_feature_importance, get_model_accuracy

# Verify they are LangChain tools (have the right attributes)
for t in [get_prediction, get_feature_importance, get_model_accuracy]:
    print(f"Tool: {t.name}")
    print(f"  Description: {t.description[:80]}...")
    print(f"  Args schema: {t.args_schema.schema() if t.args_schema else 'None'}")
    print()

print("All ML tools are valid LangChain tools.")
print("Agents can now call these via create_react_agent().")
