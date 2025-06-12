from typing import TypedDict
import json

from langgraph.graph import StateGraph, END, START
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import MessagesState
from langgraph.constants import Send

from graphs.config_provider import get_config
from graphs.llm_provider import get_llm_manager
from utilities.file_management import read_files, write_file_to_path
from utilities.generate_tree_graph import generate_package_list

prompt = """
You are a senior software engineer and your task today is to understand 
and summarize the architecture of a project. You will be given a project
directory structure and you will be able to retrieve files of interest 
you may want to inspect in order to understand things like the framework
being used, persistence, messaging systems, service responsibilities.
Being fiscally conservative engineer that wants results quickly, you should
not analyze all files but only ones that are crucial to your understanding. 

Below is the project structure
{structure}

Respond with all the files you would like to see in order to understand more 
more about the application. Only respond in json format like the following
exmample: '{{"files_to_read":["file1.py","util/file2.py"]}}'

Here are the files you have already read: {read_files}
"""

analyze_file_prompt="""
You are a senior software engineer trying to analyze this files role in the larger
context of the project. You will come up with a summary of the file.

{file_name}

{file_content}
"""

summarizer_prompt="""
You are summarizing multiple LLM answers into one concise and helpful response for a developer. 
Summarize the project features, where code responsible for certain features resides, dependencies 
and configurations. Preserve useful code and explanations.
"""

class InputState(MessagesState):
    files_to_read: list[str] = []
    project_structure: str = ""
    summary: str = ""

def generate_init_context(state: InputState):
    directoryGraph = generate_package_list(get_config()["project-root"])
    formattedPrompt = prompt.format(structure=directoryGraph,read_files="[]")
    return {
        "messages": [HumanMessage(content=formattedPrompt)], "project_structure": directoryGraph
    }

def planner_node(state: InputState):
    llm = get_llm_manager().get_llm()
    ai_message = llm.invoke(state["messages"])
    content = json.loads(ai_message.content)
    return {"messages":[ai_message], "files_to_read":content["files_to_read"]}

def continue_to_analyze_files(state: InputState):
    return [Send("file_analyzer", {"file": f, "project_root": get_config()["project-root"]}) for f in state["files_to_read"]]

class AnalyzerState(TypedDict):
    file: str
    project_root: str

def file_analyzer_node(state: AnalyzerState):
    llm = get_llm_manager().get_llm()
    file_content = read_files(state["file"], state["project_root"])
    message = HumanMessage(content=analyze_file_prompt.format(file_content=file_content, file_name=state["file"]))
    return {"messages":[llm.invoke([message])]}

def summarizer_node(state: InputState):
    response = get_llm_manager().llm.invoke(state["messages"] + [HumanMessage(summarizer_prompt)])
    write_file_to_path("summary.md", get_config()["project-root"], response.content)
    return {"messages": [response], "summary": response.content}

def build_graph():
    builder = StateGraph(InputState)
    builder.add_node("generate_init_context", generate_init_context)
    builder.add_node("planner", planner_node)
    builder.add_node("file_analyzer", file_analyzer_node)
    builder.add_node("summarizer", summarizer_node)

    builder.add_edge(START, "generate_init_context")
    builder.add_edge("generate_init_context", "planner")
    builder.add_conditional_edges(
        "planner",
        continue_to_analyze_files,
        ["file_analyzer"]
    )
    builder.add_edge("file_analyzer", "summarizer")
    builder.add_edge("summarizer", END)

    return builder