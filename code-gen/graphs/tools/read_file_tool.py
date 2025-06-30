from pathlib import Path
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig


@tool(parse_docstring=True)
def read_file(files: list[str], config: RunnableConfig) -> list[str]:
    """Read repository files, such as a class file, from the current working directory/repository.
    Useful if the task at hand is to modify a class or create a test class for a particular class.

    Args:
        files: The files to read. Must include the path
            to each file. For example, to retrieve AuditLogController.kt and build.gradle.kts,
            pass in
            ["audit-log-service/src/main/kotlin/com/foo/baz/controllers/AuditLogController.kt",
            "audit-log-service/build.gradle.kts"]
        config: (injected) Runnable config for LangChain; not required from the user.

    Returns:
        List[str]: The contents of the provided files, in the same order as the input list.
    """
    project_root = Path(config["configurable"]["project-root"])
    contents = []

    for file in files:
        full_path = project_root / file
        absolute_path = full_path.resolve()
        with open(absolute_path, "r", encoding="utf-8") as f:
            contents.append(f.read())

    return contents