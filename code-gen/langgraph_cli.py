from pathlib import Path

from langgraph.checkpoint.memory import MemorySaver

from graphs.config_provider import get_config
from graphs.main_graph import build_graph
from utilities.file_management import read_files
from utilities.generate_tree_graph import generate_package_list


def init_state():
    project_root = get_config()["project-root"]
    summary_path = Path(get_config()["project-root"]) / "summary.md"
    if summary_path.exists():
        existing_summary = read_files("summary.md", project_root)
    else:
        existing_summary = ""
    project_structure = generate_package_list(get_config()["project-root"])
    return {"messages": [], "files_to_read": [], "file_contents": [], "cli_input": "", "summary": existing_summary, "project_structure": project_structure}


def main():
    memory = MemorySaver()
    main_graph = build_graph().compile(interrupt_before=["human_input","human_approval_of_executor"], checkpointer=memory)
    thread = {
        "recursion_limit": 100,
        "configurable": {
            "thread_id": "3",
            "project-root": get_config()["project-root"]
        }
    }

    initState = init_state()

    # invocation should bring us to interrupt node for human input
    main_graph.stream(initState, thread, stream_mode="values")

    print("What would you like help with?")

    while True:
        user_input = input(">>>")
        main_graph.update_state(thread, {"cli_input": user_input}, as_node="human_input")

        for event in main_graph.stream(None, thread, stream_mode="values", config={"recursion_limit": 100}):
            if len(event["messages"]) > 0:
                event["messages"][-1].pretty_print()

        if event["messages"][-1].content.startswith("Goodbye"):
            break

if __name__ == "__main__":
    main()