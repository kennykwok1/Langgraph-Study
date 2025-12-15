from langgraph.graph import StateGraph
from typing import TypedDict
from PIL import Image as PILImage
from langchain_core.messages import HumanMessage
from dotenv import load_dotenv
import io

class State(TypedDict):
    messages: list
    counter: int

def node_a(state):
    print("Node A executed")
    state["counter"] += 1
    return state

def node_b(state):
    print("Node B executed")
    state["messages"].append("B was here")
    return state

def node_c(state):
    print("Node C executed")
    state["messages"].append("C was here")
    return state

# Create the graph
graph = StateGraph(State)

# Add nodes
graph.add_node("A", node_a)
graph.add_node("B", node_b)
graph.add_node("C", node_c)

# Add edges
graph.add_edge("A", "B")
graph.add_edge("B", "C")

# Set entry point
graph.set_entry_point("A")
graph.set_finish_point("C")

# Compile and run
app = graph.compile()

# Display the graph
img_bytes = app.get_graph().draw_mermaid_png()
PILImage.open(io.BytesIO(img_bytes)).show()


initial_state = {"messages": [], "counter": 0}
result = app.invoke(initial_state)  # type: ignore

print("Final state:", result)