from langgraph.graph import StateGraph, END

def noop_node(state: dict):
    state["log"] = state.get("log", []) + ["noop"]
    return state

graph = StateGraph(dict)
graph.add_node("concierge", noop_node)
graph.add_node("scheduler", noop_node)
graph.add_node("research", noop_node)
graph.add_node("sequencer", noop_node)
graph.add_node("analytics", noop_node)

graph.add_edge("concierge", "scheduler")
graph.add_edge("scheduler", "analytics")
graph.add_edge("research", "sequencer")
graph.add_edge("sequencer", "analytics")
graph.add_edge("analytics", END)

app = graph.compile()
