from collections import deque
from typing import Literal

from langgraph.graph import MessagesState
from langgraph.graph import StateGraph, END, START
from langgraph.types import Command, interrupt


class MainState(MessagesState):
    cli_input: str = ""
    files_to_read: list[str] = []
    project_structure: str = ""
    summary: str = ""
    tasks: deque[str]
    current_task: str


def human_approval_node(state: MainState):
    """Human node with validation."""
    question = "Would you like to write the generated file? (y/n)"

    while True:
        answer = interrupt(question)

        # Validate answer, if the answer isn't valid ask for input again.
        if answer.strip().lower() not in {"yes", "y", "no", "n"}:
            question = f"'{answer} is not a valid answer. "
            answer = None
            continue
        else:
            # If the answer is valid, we can proceed.
            break

    return {
        "cli_input": answer
    }


def write_file_node(state: MainState):
    print("You wrote the file")


# evaluate the state update from humal_approval_node
def router(state: MainState) -> Command[Literal["write_file", "__end__"]]:
    if state["cli_input"] in {"yes", "y"}:
        return Command(goto="write_file")
    else:
        return Command(goto=END)


def build_write_file_graph():
    builder = StateGraph(MainState)
    builder.add_node("human_approval", human_approval_node)
    builder.add_node("router", router)
    builder.add_node("write_file", write_file_node)

    builder.add_edge(START, "human_approval")
    builder.add_edge("human_approval", "router")
    builder.add_edge("write_file", END)
    return builder