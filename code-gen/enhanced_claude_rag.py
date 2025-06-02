import yaml
import json
import os
import sys
import argparse
import time
from functools import lru_cache
from typing import Dict, List, Optional
from pathlib import Path
from langchain_anthropic import ChatAnthropic
from langchain_community.vectorstores import Qdrant
from langchain_community.embeddings import HuggingFaceEmbeddings
from qdrant_client import QdrantClient
from langchain.prompts import PromptTemplate, ChatPromptTemplate
from langchain_core.runnables import RunnableMap

from project_context import ProjectContext
from file_operations import FileOperations

def load_config(config_path: str = "config.yaml") -> dict:
    """Load configuration from specified YAML file."""
    config_file = Path(config_path)
    
    if not config_file.exists():
        print(f"❌ Config file not found: {config_path}")
        print(f"Expected location: {config_file.absolute()}")
        
        # Offer to create a default config
        create_default = input("Would you like to create a default config file? (y/N): ").lower().strip()
        if create_default == 'y':
            create_default_config(config_file)
        else:
            sys.exit(1)
    
    try:
        with open(config_file, "r") as f:
            config = yaml.safe_load(f)
        print(f"✅ Loaded config from: {config_file.absolute()}")
        return config
    except yaml.YAMLError as e:
        print(f"❌ Error parsing YAML config: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error loading config: {e}")
        sys.exit(1)

def create_default_config(config_path: Path):
    """Create a default configuration file."""
    default_config = {
        "llm": {
            "provider": "anthropic",
            "model": "claude-3-7-sonnet-20250219",
            "temperature": 0.2,
            "api_key": "your-claude-api-key-here"
        },
        "qdrant": {
            "host": "localhost",
            "port": 6333,
            "collection_name": "kotlin-code"
        },
        "retriever": {
            "top_k": 10
        },
        "agents": {
            "planner": {
                "minDecomposedQuestions": 1,
                "maxDecomposedQuestions": 10
            }
        },
        "embedding": {
            "model": "BAAI/bge-small-en-v1.5"
        }
    }
    
    try:
        with open(config_path, 'w') as f:
            yaml.dump(default_config, f, default_flow_style=False, indent=2)
        print(f"✅ Created default config at: {config_path.absolute()}")
        print("⚠️  Please edit the config file and add your Claude API key before running again.")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Error creating default config: {e}")
        sys.exit(1)

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Enhanced RAG Code Assistant with project awareness",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python enhanced_claude_rag.py
  python enhanced_claude_rag.py --config /path/to/my-config.yaml
  python enhanced_claude_rag.py -c production.yaml
  python enhanced_claude_rag.py --config ../configs/team-config.yaml
        """
    )
    
    parser.add_argument(
        "-c", "--config",
        default="config.yaml",
        help="Path to configuration YAML file (default: config.yaml)"
    )
    
    parser.add_argument(
        "--project-root",
        default=".",
        help="Root directory of the project to analyze (default: current directory)"
    )
    
    parser.add_argument(
        "--version",
        action="version",
        version="Enhanced RAG Code Assistant 1.0"
    )
    
    return parser.parse_args()

# Parse command line arguments
args = parse_arguments()

# Load config from specified file
config = load_config(args.config)

# Initialize components
llm = ChatAnthropic(
    model=config["llm"]["model"],
    temperature=config["llm"]["temperature"],
    api_key=config["llm"]["api_key"],
    max_tokens=config["llm"]["max_tokens"],
)

qdrant_client = QdrantClient(
    host=config["qdrant"]["host"],
    port=config["qdrant"]["port"]
)

collection_name = config["qdrant"]["collection_name"]
embedding_model = HuggingFaceEmbeddings(model_name=config["embedding"]["model"])

vectorstore = Qdrant(
    client=qdrant_client,
    collection_name=collection_name,
    embeddings=embedding_model,
    content_payload_key="code"
)

retriever = vectorstore.as_retriever(search_kwargs={"k": config["retriever"]["top_k"]})

# Initialize context and file operations with project root from args
project_context = ProjectContext(args.project_root)
file_ops = FileOperations(args.project_root)

def estimate_tokens(text: str) -> int:
    """Rough estimate of tokens (1 token ≈ 4 characters for English)."""
    return len(text) // 4

def truncate_retrieved_content(retrieved_docs, max_tokens: int = 3000) -> str:
    """Truncate retrieved content to fit within token limits."""
    if not retrieved_docs:
        return "No relevant code found."
    
    content_parts = []
    current_tokens = 0
    
    for doc in retrieved_docs[:10]:  # Limit to first 10 documents
        doc_content = getattr(doc, 'page_content', str(doc))
        if hasattr(doc, 'metadata'):
            metadata = doc.metadata
            doc_text = f"// From: {metadata.get('symbol', 'unknown')}\n{doc_content}"
        else:
            doc_text = doc_content
        
        doc_tokens = estimate_tokens(doc_text)
        if current_tokens + doc_tokens > max_tokens:
            # Truncate this document to fit
            remaining_tokens = max_tokens - current_tokens
            if remaining_tokens > 100:  # Only add if we have reasonable space
                truncated_chars = remaining_tokens * 4
                doc_text = doc_text[:truncated_chars] + "..."
                content_parts.append(doc_text)
            break
        
        content_parts.append(doc_text)
        current_tokens += doc_tokens
    
    return "\n\n---\n\n".join(content_parts)

def invoke_llm_with_retry(chain, input_data, max_retries=3, base_delay=2):
    """Invoke LLM with exponential backoff retry logic and token monitoring."""
    
    # Estimate total input size
    input_str = str(input_data)
    estimated_tokens = estimate_tokens(input_str)
    
    if estimated_tokens > 8000:  # Conservative limit
        print(f"⚠️  Large input detected (~{estimated_tokens} tokens). This might cause issues.")
    
    for attempt in range(max_retries):
        try:
            return chain.invoke(input_data)
        except Exception as e:
            error_msg = str(e).lower()
            
            # Check if it's a retryable error
            if any(keyword in error_msg for keyword in ['overloaded', '529', 'rate limit', 'timeout', 'connection', 'token']):
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)  # Exponential backoff
                    print(f"⏳ Claude API issue (attempt {attempt + 1}/{max_retries})")
                    print(f"   Error: {str(e)[:100]}...")
                    print(f"   Retrying in {delay} seconds...")
                    time.sleep(delay)
                    continue
                else:
                    print(f"❌ Claude API still unavailable after {max_retries} attempts")
                    print(f"   Error: {e}")
                    print(f"   Try reducing context size or check your API key")
                    raise
            else:
                # Non-retryable error, raise immediately
                raise
    
    return None

# Cached Qdrant search
@lru_cache(maxsize=100)
def cached_retrieve(query: str):
    try:
        return retriever.invoke(query)
    except Exception as e:
        print(f"⚠️  Warning: Retrieval failed for query: {query[:50]}...")
        print(f"   Error: {e}")
        return []

# Enhanced prompts with project context
context_aware_prompt = PromptTemplate.from_template("""
You are a senior Kotlin/TypeScript engineer working on this specific project. Use the project context and retrieved code examples to provide accurate, project-specific solutions.

PROJECT CONTEXT:
{project_context}

RETRIEVED CODE EXAMPLES:
{retrieved_code}

QUESTION:
{question}

Instructions:
- Follow the existing project structure and naming conventions
- Use the same package structure and architectural patterns
- Reference specific files and classes from the project when relevant
- Provide complete, working code that fits the project's style
""")

# File operation prompt
file_operation_prompt = PromptTemplate.from_template("""
You are a senior Kotlin engineer helping to create or modify files in this project.

PROJECT CONTEXT:
{project_context}

RETRIEVED CODE EXAMPLES:
{retrieved_code}

USER REQUEST:
{question}

CURRENT FILE CONTENT (if modifying existing file):
{current_file_content}

Instructions:
1. Analyze the request and determine if it requires:
   - Creating a new file
   - Modifying an existing file
   - Creating directories

2. Follow the project's existing patterns and conventions
3. Provide your response in this JSON format:

{{
    "analysis": "Brief explanation of what needs to be done",
    "operations": [
        {{
            "type": "create_file|modify_file|create_directory",
            "path": "relative/path/to/file",
            "content": "full file content for create_file",
            "modifications": [
                {{
                    "type": "replace|insert_at_line|append|prepend",
                    "old_text": "text to replace (for replace type)",
                    "new_text": "new text to insert",
                    "line_number": 10
                }}
            ]
        }}
    ],
    "explanation": "Detailed explanation of the solution and why these files/changes are needed"
}}

Only include the 'modifications' field for modify_file operations.
Only include the 'content' field for create_file operations.
""")

# Planning prompt for complex requests
planner_prompt = ChatPromptTemplate.from_template("""
You are an experienced Kotlin engineer helping to plan a development task.

PROJECT CONTEXT:
{project_context}

Given this request, break it down into 2-4 focused sub-questions that would help retrieve relevant code examples and implement the solution.

Consider:
- What existing patterns in the codebase are relevant?
- What components need to be created or modified?
- What architectural concerns need to be addressed?

Request: {question}

Respond with a numbered list of specific, actionable sub-questions.
""")

# Chains with optimized context
planner_chain = planner_prompt | llm

context_aware_chain = RunnableMap({
    "project_context": lambda x: project_context.get_focused_context(x["question"], 1000),
    "retrieved_code": lambda x: truncate_retrieved_content(cached_retrieve(x["question"]), 2500),
    "question": lambda x: x["question"]
}) | context_aware_prompt | llm

file_operation_chain = RunnableMap({
    "project_context": lambda x: project_context.get_focused_context(x["question"], 800),
    "retrieved_code": lambda x: truncate_retrieved_content(cached_retrieve(x["question"]), 2000),
    "question": lambda x: x["question"],
    "current_file_content": lambda x: x.get("current_file_content", "")[:1000] + ("..." if len(x.get("current_file_content", "")) > 1000 else "")
}) | file_operation_prompt | llm

def execute_file_operations(operations_json: str) -> List[str]:
    """Execute file operations based on LLM response."""
    results = []
    
    try:
        operations_data = json.loads(operations_json)
        operations = operations_data.get("operations", [])
        
        for op in operations:
            op_type = op.get("type")
            path = op.get("path")
            
            if op_type == "create_file":
                content = op.get("content", "")
                success, message = file_ops.create_file(path, content)
                results.append(f"Create {path}: {message}")
                
            elif op_type == "modify_file":
                modifications = op.get("modifications", [])
                success, message = file_ops.modify_file(path, modifications)
                results.append(f"Modify {path}: {message}")
                
            elif op_type == "create_directory":
                success, message = file_ops.create_directory(path)
                results.append(f"Create directory {path}: {message}")
                
    except json.JSONDecodeError as e:
        results.append(f"Error parsing operations JSON: {e}")
    except Exception as e:
        results.append(f"Error executing operations: {e}")
    
    return results

def run_enhanced_rag(question: str, execute_operations: bool = False) -> str:
    """Run the enhanced RAG system with project context and file operations."""
    
    # Check if this is a file operation request
    file_operation_keywords = [
        "create", "generate", "add", "implement", "build", "make",
        "file", "class", "service", "controller", "repository",
        "modify", "update", "change", "fix", "refactor"
    ]
    
    is_file_operation = any(keyword in question.lower() for keyword in file_operation_keywords)
    
    if is_file_operation and execute_operations:
        # Use file operation workflow
        print("🔧 Planning file operations...")
        
        # Get current file content if modifying
        current_file_content = ""
        if "modify" in question.lower() or "update" in question.lower():
            # Try to extract file path from question or ask user
            print("Note: If modifying an existing file, specify the file path")
        
        # Generate file operations
        response = invoke_llm_with_retry(file_operation_chain, {
            "question": question,
            "current_file_content": current_file_content
        })
        
        # Parse and execute operations
        operations_json = response.content.strip()
        print(f"\n📋 Planned Operations:\n{operations_json}")
        
        # Confirm before executing
        confirm = input("\n⚠️  Execute these operations? (y/N): ").lower().strip()
        if confirm == 'y':
            results = execute_file_operations(operations_json)
            print(f"\n✅ Execution Results:")
            for result in results:
                print(f"  {result}")
            return operations_json
        else:
            print("Operations cancelled.")
            return operations_json
    
    else:
        # Use regular context-aware RAG
        print("🔍 Analyzing project and retrieving relevant code...")
        
        # Step 1: Plan the approach
        plan_response = invoke_llm_with_retry(planner_chain, {
            "question": question,
            "project_context": project_context.get_focused_context(question, 800)
        })
        raw_plan = plan_response.content.strip()
        print(f"\n📋 Analysis Plan:\n{raw_plan}")
        
        # Step 2: Parse sub-questions
        subquestions = [
            line.split(". ", 1)[1].strip()
            for line in raw_plan.splitlines()
            if ". " in line and line.strip()
        ]
        
        # Step 3: Get context-aware answers
        answers = []
        for sub in subquestions:
            print(f"\n🔎 Researching: {sub}")
            result = invoke_llm_with_retry(context_aware_chain, {"question": sub})
            answers.append((sub, result.content.strip()))
        
        # Step 4: Synthesize final answer
        if len(answers) > 1:
            subanswer_text = "\n\n".join(f"Q: {q}\nA: {a}" for q, a in answers)
            
            synthesis_prompt = PromptTemplate.from_template("""
            Synthesize these project-specific answers into one comprehensive solution:
            
            PROJECT CONTEXT:
            {project_context}
            
            SUB-ANSWERS:
            {subanswers}
            
            Provide a clear, actionable solution that follows the project's patterns and conventions.
            """)
            
            synthesis_chain = synthesis_prompt | llm
            
            # Truncate subanswers if too long
            max_subanswer_length = 4000
            if len(subanswer_text) > max_subanswer_length:
                subanswer_text = subanswer_text[:max_subanswer_length] + "\n\n[Additional answers truncated...]"
            
            final_response = invoke_llm_with_retry(synthesis_chain, {
                "project_context": project_context.get_focused_context(question, 600),
                "subanswers": subanswer_text
            })
            
            return final_response.content
        else:
            return answers[0][1] if answers else "No relevant information found."

def interactive_mode():
    """Run the interactive enhanced RAG system."""
    print("🚀 Enhanced RAG Code Assistant")
    print("=" * 50)
    print(f"📁 Project: {project_context.root_path}")
    print(f"⚙️  Config: {Path(args.config).absolute()}")
    print(f"🤖 Model: {config['llm']['model']}")
    
    # Show project context
    structure = project_context.scan_project_structure()
    print(f"📦 Package: {structure['patterns']['package_structure'].get('common_root', 'None')}")
    print(f"🏗️  Architecture: {', '.join(structure['patterns']['common_patterns']['architecture_patterns']) or 'Standard'}")
    print(f"📝 Kotlin files: {len(structure['kotlin_files'])}")
    print(f"📂 Directories: {len(structure['directories'])}")
    
    print("\nType 'exit' to quit, 'help' for commands")
    print("Add '--execute' to your question to perform file operations")
    print("-" * 50)
    
    while True:
        try:
            question = input("\n💭 What would you like help with?\n> ").strip()
            
            if not question:
                continue
                
            if question.lower() == 'exit':
                break
                
            if question.lower() == 'help':
                print("""
Available commands:
- Ask any coding question
- Add '--execute' to perform file operations
- 'backups' - List available backups
- 'context' - Show project context
- 'structure' - Show project structure
- 'status' - Check API connectivity
- 'exit' - Quit
                """)
                continue
                
            if question.lower() == 'backups':
                backups = file_ops.list_backups()
                if backups:
                    print(f"\n📁 Available backups ({len(backups)}):")
                    for backup in backups[:10]:
                        print(f"  {backup['name']} ({backup['size']} bytes, {backup['created']})")
                else:
                    print("No backups found.")
                continue
                
            if question.lower() == 'context':
                print(f"\n{project_context.to_context_string()}")
                continue
                
            if question.lower() == 'structure':
                structure = project_context.scan_project_structure()
                print(f"\n📊 Project Structure:")
                print(json.dumps(structure, indent=2, default=str))
                continue
                
            if question.lower() == 'status':
                print("\n🔍 Checking API connectivity...")
                try:
                    # Test Claude API
                    test_response = invoke_llm_with_retry(llm, "Hello")
                    print("✅ Claude API: Connected")
                    
                    # Test Qdrant
                    try:
                        collection_info = qdrant_client.get_collection(collection_name)
                        vector_count = qdrant_client.count(collection_name)
                        print(f"✅ Qdrant: Connected ({vector_count.count} vectors in '{collection_name}')")
                    except Exception as e:
                        print(f"❌ Qdrant: Connection failed - {e}")
                        
                except Exception as e:
                    print(f"❌ Claude API: Connection failed - {e}")
                continue
            
            execute_ops = '--execute' in question
            if execute_ops:
                question = question.replace('--execute', '').strip()
            
            print(f"\n🤖 Processing: {question}")
            response = run_enhanced_rag(question, execute_operations=execute_ops)
            
            print(f"\n💡 Response:")
            print(response)
            
        except KeyboardInterrupt:
            print("\n\nGoodbye! 👋")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")

if __name__ == "__main__":
    interactive_mode()