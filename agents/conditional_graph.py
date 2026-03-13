"""
conditional_graph.py — A graph with conditional edges.

CONCEPT: Conditional edges let the graph make decisions.
         "If X, go to node A. Otherwise, go to node B."
         This is how agents make choices.

This graph decides whether cricket analysis is "exciting" or "boring"
based on Gemini's response, and routes to different nodes.
"""


from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv

load_dotenv()


class AnalysisState(TypedDict):
    messages: Annotated[list, add_messages]
    topic: str
    sentiment: str  # "exciting" or "boring"
    final_output: str


def analyze_topic(state: AnalysisState) -> dict:
    """Analyze the topic and determine sentiment."""
    llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash")
    response = llm.invoke(
        f"Is '{state['topic']}' an exciting or boring cricket topic? "
        f"Reply with ONLY the word 'exciting' or 'boring'."
    )
    sentiment = "exciting" if "exciting" in response.content.lower() else "boring"
    print(f"  [analyze] Topic '{state['topic']}' is: {sentiment}")
    return {"sentiment": sentiment}


def exciting_response(state: AnalysisState) -> dict:
    """Handle exciting topics with enthusiasm."""
    output = f"Great topic! '{state['topic']}' is fascinating. Let's dive deep!"
    print(f"  [exciting] {output}")
    return {"final_output": output}


def boring_response(state: AnalysisState) -> dict:
    """Handle boring topics with a suggestion."""
    output = f"'{state['topic']}' is a bit dry. How about analyzing player strike rates instead?"
    print(f"  [boring] {output}")
    return {"final_output": output}


# ─────────────────────────────────────────────────
# The key concept: CONDITIONAL EDGES
# ─────────────────────────────────────────────────
def route_by_sentiment(state: AnalysisState) -> str:
    """This function returns the NAME of the next node.
    LangGraph calls this after 'analyze' to decide where to go."""
    if state["sentiment"] == "exciting":
        return "exciting_response"
    else:
        return "boring_response"


# Build the graph
graph_builder = StateGraph(AnalysisState)

graph_builder.add_node("analyze", analyze_topic)
graph_builder.add_node("exciting_response", exciting_response)
graph_builder.add_node("boring_response", boring_response)

graph_builder.add_edge(START, "analyze")

# CONDITIONAL EDGE: after "analyze", call route_by_sentiment to decide next node
graph_builder.add_conditional_edges(
    "analyze",                  # Source node
    route_by_sentiment,         # Function that returns the next node name
    {                           # Map of possible destinations
        "exciting_response": "exciting_response",
        "boring_response": "boring_response",
    }
)

graph_builder.add_edge("exciting_response", END)
graph_builder.add_edge("boring_response", END)

graph = graph_builder.compile()

# Save graph visualization as PNG
png_data = graph.get_graph().draw_mermaid_png()
with open("conditional_graph.png", "wb") as f:
    f.write(png_data)
print("Graph saved to conditional_graph.png")



if __name__ == "__main__":
    print("=" * 50)
    print("Conditional Edge Graph")
    print("=" * 50)

    # Test with different topics
    for topic in ["Virat Kohli's T20 strike rate", "MS Dhoni's IPL stats"]:
        print(f"\nTopic: {topic}")
        result = graph.invoke({
            "topic": topic,
            "messages": [],
            "sentiment": "",
            "final_output": "",
        })
        print(f"Result: {result['final_output']}")
    

