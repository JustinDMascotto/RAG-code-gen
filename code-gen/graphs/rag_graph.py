import json
from collections import deque
from typing import Literal

from langgraph.prebuilt import ToolNode
from langgraph.graph import MessagesState
from langgraph.graph import StateGraph, END, START
from langgraph.types import Command
from langchain_core.messages import HumanMessage, SystemMessage, RemoveMessage
from graphs.llm_provider import get_llm_manager
from graphs.tools.read_file_tool import read_file
from graphs.tools.vector_store_tool import retrieve_relevant_code

planner_node_system_prompt="""
You are a senior software engineer. It is your job to interpret any question being asked and decompose 
it into smaller more focused tasks. You should only respond in json format. For instance, if you were 
asked "Create a persistence layer for model X with basic CRUD operations", you might respond with 
'{{"tasks":["Create DAO class for model X with basic CRUD operations","Create unit test for the DAO class"]}}'

Limit the number of tasks to 3.

Here is a summary of the project for context:
{summary}
"""

executor_prompt="""
Evaluate your given task with the provided project structure and summary. Make sure to include the 
technology names and keywords and non domain-speific tooling class names and methods when querying 
using the retrieve_relevant_code tool. You should read all the domain models in order to accurately 
construct them to pass them into methods.


Structure:
{project_structure}

Summary:
{summary}
"""

class MainState(MessagesState):
    cli_input: str = ""
    files_to_read: list[str] = []
    project_structure: str = ""
    summary: str = ""
    tasks: deque[str]
    current_task: str

tools = [read_file,retrieve_relevant_code]
llm_with_tools = get_llm_manager().get_llm().bind_tools(tools)

def planner_node(state: MainState):
    system_msg = planner_node_system_prompt.format(summary=state["summary"])
    response = get_llm_manager().get_llm().invoke([system_msg,HumanMessage(content=state["cli_input"])])
    tasks = json.loads(response.content)["tasks"]
    return {"messages":[response], "tasks":deque(tasks)}

def filter_messages(state: MessagesState):
    """
    Remove all messages that are:
    - AI messages that include tool calls
    - Tool response messages
    """
    messages = state["messages"]

    delete_messages = [
        RemoveMessage(id=m.id)
        for m in messages
        if (
            # tool call message from AI
            getattr(m, "tool_calls", None)
                and isinstance(m.tool_calls, list)
                and len(m.tool_calls) > 0
           )
           or (
               # tool response message
                getattr(m, "type", None) == "tool"
           )
    ]

    return {"messages": delete_messages}

def continue_to_task_node(state: MainState) -> Command[Literal["executor", "__end__"]]:
    tasks: deque[str] = state["tasks"]
    returnCommand = Command(update={"current_task": ""}, goto=END)
    if not tasks or len(tasks) == 0:                       # nothing left
        return returnCommand

    next_task = tasks.popleft()
    if next_task == "":
        return returnCommand
    return Command(update={"current_task": next_task}, goto="executor")

def executor_node(state: MainState):
    response = llm_with_tools.invoke( state["messages"] + [SystemMessage(executor_prompt.format(project_structure=state["project_structure"], summary=state["summary"])), HumanMessage(content=state["current_task"])])
    return {"messages": [response]}

tool_node = ToolNode(tools)

def should_continue(state: MessagesState):
    messages = state["messages"]
    last_message = messages[-1]
    if last_message.tool_calls:
        return "tools"
    return "filter_messages"

def build_graph():
    builder = StateGraph(MainState)
    builder.add_node("planner", planner_node)
    builder.add_node("filter_messages", filter_messages)
    builder.add_node("continue_to_task", continue_to_task_node)

    # Register the map_node (wraps a function that handles a single task)
    builder.add_node("executor", executor_node)
    builder.add_node("tools", tool_node)

    builder.add_edge(START, "planner")
    builder.add_edge("planner", "filter_messages")
    builder.add_edge("filter_messages", "continue_to_task")
    # we dont need the below edge because we have it defined in the return hint from
    # continue_to_task. see https://langchain-ai.github.io/langgraph/how-tos/graph-api/#combine-control-flow-and-state-updates-with-command
    #builder.add_edge("continue_to_task", "executor")
    #builder.add_edge("continue_to_task", END)

    builder.add_conditional_edges("executor", should_continue, ["tools", "filter_messages"])
    builder.add_edge("tools", "executor")

    return builder