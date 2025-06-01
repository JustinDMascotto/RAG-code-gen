import yaml
from functools import lru_cache
from langchain_anthropic import ChatAnthropic
from langchain_community.vectorstores import Qdrant
from langchain_community.embeddings import HuggingFaceEmbeddings
from qdrant_client import QdrantClient
from langchain.prompts import PromptTemplate, ChatPromptTemplate
from langchain_core.runnables import RunnableMap

# Load config from YAML
with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

# Claude setup
llm = ChatAnthropic(
    model=config["llm"]["model"],
    temperature=config["llm"]["temperature"],
    api_key=config["llm"]["api_key"]
)

# Qdrant setup
qdrant_client = QdrantClient(
    host=config["qdrant"]["host"],
    port=config["qdrant"]["port"]
)

collection_name = config["qdrant"]["collection_name"]

# Embeddings
embedding_model = HuggingFaceEmbeddings(model_name=config["embedding"]["model"])

# Vector store
vectorstore = Qdrant(
    client=qdrant_client,
    collection_name=collection_name,
    embeddings=embedding_model,
    content_payload_key="code"
)

retriever = vectorstore.as_retriever(search_kwargs={"k": config["retriever"]["top_k"]})

# Cached Qdrant search
@lru_cache(maxsize=100)
def cached_retrieve(query: str):
    return retriever.invoke(query)

# Prompt for code question
code_prompt = PromptTemplate.from_template("""
You are a senior Kotlin/TypeScript engineer. Use the following context from the organization's utility codebase to answer the question.

Context:
{context}

Question:
{question}
""")

# Prompt for planner agent
planner_prompt = ChatPromptTemplate.from_template("""
You are an experienced Kotlin/TypeScript engineer helping break down a request.

Given a high-level developer question, generate 2–4 focused sub-questions that would help retrieve relevant utility code.

Respond with a numbered list.

Question:
{question}
""")

# Prompt for summarizer
summarizer_prompt = PromptTemplate.from_template("""
You are summarizing multiple LLM answers into one concise and helpful response for a developer.

Preserve useful code and explanations.

Sub-Answers:
{subanswers}
""")

# Chains
planner_chain = planner_prompt | llm
qa_chain = RunnableMap({
    "context": lambda x: cached_retrieve(x["question"]),
    "question": lambda x: x
}) | code_prompt | llm
summarizer_chain = summarizer_prompt | llm

# Main execution logic
def run_multi_agent_rag(question: str):
    # Step 1: Use planner to generate sub-questions
    plan_response = planner_chain.invoke({"question": question})
    raw_plan = plan_response.content.strip()
    print("\n--- Planner Output ---\n" + raw_plan)

    # Step 2: Parse into individual questions
    subquestions = [
        line.split(". ", 1)[1].strip()
        for line in raw_plan.splitlines()
        if ". " in line
    ]

    # Step 3: Run QA chain on each subquestion
    answers = []
    for sub in subquestions:
        print(f"\nProcessing sub-question: {sub}")
        result = qa_chain.invoke({"question": sub})
        answers.append((sub, result.content.strip()))

    # Step 4: Aggregate and summarize
    subanswer_text = "\n\n".join(f"Q: {q}\nA: {a}" for q, a in answers)
    summary = summarizer_chain.invoke({"subanswers": subanswer_text})

    return summary.content

# CLI entrypoint
if __name__ == "__main__":
    question = input("What would you like help with?\n> ")
    final_answer = run_multi_agent_rag(question)
    print("\n--- Final Answer ---\n")
    print(final_answer)