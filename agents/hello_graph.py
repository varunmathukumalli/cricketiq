"""
hello_graph.py — Your first LangGraph graph.

CONCEPT: A graph is nodes (functions) connected by edges (transitions).
         State flows through the graph — each node can read and modify it.

This graph has 3 nodes:
  greet → analyze → respond

Run: python agents/hello_graph.py
"""


from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────────
# STEP 1: Define the State
# ─────────────────────────────────────────────────
# State is a TypedDict — a Python dictionary with defined fields.
# Every node in the graph can read and write to this state.
# Think of it as a shared clipboard that all agents pass around.

class HelloState(TypedDict):
    messages: Annotated[list, add_messages]  # Conversation history
    user_name: str                           # Custom data we add
    analysis: str                            # Another custom field


# ─────────────────────────────────────────────────
# STEP 2: Define the Nodes (functions)
# ─────────────────────────────────────────────────
# Each node is a function that takes state and returns updated state.
# Nodes are where the actual work happens.

def greet_node(state: HelloState) -> dict:
    """Node 1: Greet the user. No LLM needed — just Python."""
    name = state.get("user_name", "World")
    greeting = f"Hello, {name}! Welcome to CricketIQ."
    print(f"  [greet_node] {greeting}")
    return {"messages": [("assistant", greeting)]}


def analyze_node(state: HelloState) -> dict:
    """Node 2: Use Gemini to analyze something. This is where the LLM comes in."""
    llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash")
    response = llm.invoke(
        f"In one sentence, what makes cricket analytics interesting? "
        f"Address your response to {state.get('user_name', 'the user')}."
    )
    print(f"  [analyze_node] Gemini says: {response.content}")
    return {
        "messages": [("assistant", response.content)],
        "analysis": response.content,
    }


def respond_node(state: HelloState) -> dict:
    """Node 3: Combine everything into a final response."""
    analysis = state.get("analysis", "")
    final = f"Here's what I think: {analysis}"
    print(f"  [respond_node] Final: {final[:80]}...")
    return {"messages": [("assistant", final)]}


# ─────────────────────────────────────────────────
# STEP 3: Build the Graph
# ─────────────────────────────────────────────────
# This is the core of LangGraph — connecting nodes with edges.

# Create an empty graph with our state type
graph_builder = StateGraph(HelloState)

# Add nodes (register the functions)
graph_builder.add_node("greet", greet_node)
graph_builder.add_node("analyze", analyze_node)
graph_builder.add_node("respond", respond_node)

# Add edges (connect the nodes)
# START → greet → analyze → respond → END
graph_builder.add_edge(START, "greet")
graph_builder.add_edge("greet", "analyze")
graph_builder.add_edge("analyze", "respond")
graph_builder.add_edge("respond", END)

# Compile the graph (makes it runnable)
graph = graph_builder.compile()


# ─────────────────────────────────────────────────
# STEP 4: Run it!
# ─────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 50)
    print("Running your first LangGraph graph!")
    print("=" * 50)

    # Invoke the graph with initial state
    result = graph.invoke({
        "user_name": "Varun",
        "messages": [],
        "analysis": "",
    })

    print("\n" + "=" * 50)
    print("FINAL STATE:")
    print(f"  Messages: {len(result['messages'])}")
    print(f"  Analysis: {result['analysis'][:100]}...")
    print("=" * 50)

    # BONUS: Visualize the graph
    print("\nGraph structure:")
    print("  START → greet → analyze → respond → END")