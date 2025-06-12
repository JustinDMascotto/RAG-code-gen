from langchain_core.documents import Document
from langchain_core.tools import tool

from typing import Tuple

from graphs.config_provider import get_config
from utilities.retrieval_manager import RetrievalManager

retriever_manager = RetrievalManager(get_config())

@tool(parse_docstring=True)
def retrieve_relevant_code(query: str) -> list[Tuple[Document, float]]:
    """
    Given a query, retrieve documents with relevant code examples. The relevant code you can expect
    to retrieve is not specific to any domain but will provide usage examples of how tooling can and
    should be used. ie "dao mongo layer that uses SearchQueryParameters" will return exampled DAO layers
    that use SearchQueryParams that follow the company's coding standards and utilizes standard libraries.
    All this to say, try not to include domain-specific language in your
    query but include technologies, tooling class name, layer (service, controller/handler, topology, test/spec etc)
    to get usage examples.

    Args:
        query: The natural language query used to filter the most relevant code examples.

    Returns:
        A list of documents to their closeness score relative to the query.
    """
    return retriever_manager.retrieve_with_scores(query,0.8)