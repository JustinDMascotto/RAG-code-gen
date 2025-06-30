from langgraph.graph import StateGraph, END, START
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import MessagesState

from graphs.llm_provider import get_llm_manager
from graphs.init_context_graph import build_graph as build_init_graph


class MainState(MessagesState):
    cli_input: str = ""
    files_to_read: list[str] = []
    project_structure: str = ""
    summary: str = ""


# no-op node used
def human_input_node(state: MainState):
    pass


def router_node(state: MainState):
    """Route based on CLI input type."""
    user_input = state["cli_input"].lower().strip()

    if user_input == "init":
        return {"next": "init"}
    elif user_input in ["exit", "quit"]:
        return {"next": "exit"}
    else:
        return {"next": "question"}


def question_node(state: MainState):
    """Handle general questions using LLM."""
    llm = get_llm_manager().get_llm()

    question = state["cli_input"]
    print(f"\n🤖 Processing question: {question}")

    # Simple question answering
    response = llm.invoke(state["messages"] + [HumanMessage(content=question)])
    answer = response.content

    print(f"\n💡 Answer:\n{answer}")

    return {
        "messages": [HumanMessage(content=question), response]
    }


def exit_node(state: MainState):
    """Handle exit command."""
    return {
        "messages": [HumanMessage(content="Goodbye! 👋")]
    }


def build_graph():
    """Build the main CLI routing graph."""
    builder = StateGraph(MainState)

    # Add nodes
    builder.add_node("human_input", human_input_node)
    builder.add_node("router", router_node)
    builder.add_node("question_handler", question_node)
    builder.add_node("init_context_handler", build_init_graph().compile())
    builder.add_node("exit_handler", exit_node)

    # Add edges
    builder.add_edge(START, "human_input")
    builder.add_edge("human_input", "router")

    # Add conditional edges from router
    builder.add_conditional_edges(
        "router",
        lambda state: state["next"],
        {
            "question": "question_handler",
            "init": "init_context_handler",
            "exit": "exit_handler"
        }
    )

    # All handlers end the flow
    builder.add_edge("question_handler", "human_input")
    builder.add_edge("init_context_handler", "human_input")
    builder.add_edge("exit_handler", END)

    return builder