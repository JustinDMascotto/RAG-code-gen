# ASTparser

A complete RAG (Retrieval-Augmented Generation) pipeline for Kotlin code analysis, semantic search, and AI-powered code generation.

## Overview

This project implements a full RAG architecture with three main components that work together to parse, index, and generate code:

1. **ast-parser** - Parses Kotlin files and extracts code declarations
2. **qdrant-import** - Imports parsed code into Qdrant vector database with embeddings
3. **code-gen** - AI-powered code generation using Claude with retrieval from the code database

## Architecture

```
┌─────────────────┐    JSONL    ┌─────────────────┐    HTTP    ┌─────────────────┐
│   ast-parser    │ ──────────► │ qdrant-import   │ ─────────► │     Qdrant      │
│                 │             │                 │            │   Vector DB     │
│ • Parse .kt/.kts│             │ • Generate      │            │                 │
│ • Extract funcs │             │   embeddings    │            │ • Store vectors │
│ • Extract classes│             │ • Batch upload  │            │ • Enable search │
│ • Output JSONL  │             │ • Error handling│            │                 │
└─────────────────┘             └─────────────────┘            └─────────────────┘
                                                                          ▲
                                                                          │
                                                                    Retrieval
                                                                          │
┌─────────────────┐    Question  ┌─────────────────┐ ─────────────────────┘
│      User       │ ──────────► │   code-gen      │
│                 │             │   (RAG System)  │
│ • Ask questions │             │                 │
│ • Get solutions │   Response  │ • Multi-agent   │
│ • Code examples │ <────────── │ • Query planning│
└─────────────────┘             │ • Answer synthesis│
                                └─────────────────┘
                                          │
                                          │ API Calls
                                          ▼
                                ┌─────────────────┐
                                │   Claude API    │
                                │                 │
                                │ • Code generation│
                                │ • Natural language│
                                │ • Context-aware  │
                                └─────────────────┘
```

## Components

### ast-parser

The AST parser processes Kotlin source code and extracts function and class declarations.

**Features:**
- Recursive directory scanning for `.kt` and `.kts` files
- Extracts functions, classes, and their metadata
- Multiple output formats: JSONL, JSON, human-readable summary
- Command-line interface for batch processing

**Output Structure:**
Each declaration is output as a JSON object containing:
- `id` - Unique identifier
- `file_path` - Source file location
- `symbol` - Function/class name with namespace
- `kind` - Type of declaration (function, class)
- `code` - Full source code of the declaration
- `metadata` - Modifiers, annotations, parent class info

### qdrant-import

The Qdrant import tool streams JSONL data into a Qdrant vector database.

**Features:**
- Streams JSONL input from stdin
- Automatic Qdrant collection creation
- Configurable batch processing
- Embedding generation (with fallback to random vectors)
- Error handling and progress reporting

**Workflow:**
1. Reads JSONL from stdin line by line
2. Generates vector embeddings for code text
3. Batches records for efficient upload
4. Creates/updates Qdrant collection with points

### code-gen

The RAG-powered code generation system that uses Claude AI to answer questions and generate code based on your indexed codebase.

**Features:**
- Multi-agent query planning and decomposition
- Semantic retrieval from Qdrant vector database
- Context-aware code generation using Claude
- Answer synthesis and summarization
- Interactive CLI interface

**Multi-Agent Workflow:**
1. **Planner Agent**: Breaks down complex questions into focused sub-questions
2. **Retrieval Agent**: Searches vector database for relevant code examples
3. **QA Agent**: Answers each sub-question using retrieved context
4. **Summarizer Agent**: Combines multiple answers into a coherent response

## Quick Start

### Prerequisites

- Java 17+
- Docker (for Qdrant)
- Python 3.8+ with uvicorn (for embedding service, optional)
- Python 3.8+ with pip (for code-gen module)
- Claude API key from Anthropic

### 1. Start Qdrant Vector Database

```bash
docker run -d --name qdrant \
  -p 6333:6333 \
  -p 6334:6334 \
  -v $(pwd)/qdrant_storage:/qdrant/storage:z \
  qdrant/qdrant
```

This starts Qdrant with:
- REST API on port 6333
- gRPC API on port 6334
- Persistent storage in `./qdrant_storage`

### 2. Start Embedding Service (Optional)

For semantic embeddings instead of random vectors, start an embedding service:

```bash
# Install dependencies
pip install uvicorn fastapi sentence-transformers

# Create a simple embedding service (embedding_service.py)
cat > embedding_service.py << 'EOF'
from fastapi import FastAPI
from sentence_transformers import SentenceTransformer
from typing import List
import uvicorn

app = FastAPI()
model = SentenceTransformer('all-MiniLM-L6-v2')

@app.post("/embed")
async def embed_texts(request: dict):
    texts = request.get("texts", [])
    if not texts:
        return {"embeddings": [[0.0] * 384]}
    
    embeddings = model.encode(texts).tolist()
    return {"embeddings": embeddings}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
EOF

# Start the embedding service
uvicorn embedding_service:app --host 0.0.0.0 --port 8000
```

The embedding service will run on `http://localhost:8000` and provide semantic embeddings for code chunks.

### 3. Build the Tools

```bash
./gradlew build
```

### 3. Parse Kotlin Code

```bash
# Parse files and output JSONL
java -jar ast-parser/build/libs/ast-parser-1.0-SNAPSHOT.jar \
  --output=jsonl \
  /path/to/kotlin/project > code_chunks.jsonl

# Or parse specific files
java -jar ast-parser/build/libs/ast-parser-1.0-SNAPSHOT.jar \
  --output=jsonl \
  MyClass.kt AnotherFile.kts > code_chunks.jsonl
```

### 4. Import to Qdrant

```bash
# Import with automatic collection creation
cat code_chunks.jsonl | java -jar qdrant-import/build/libs/qdrant-import-1.0-SNAPSHOT.jar \
  --collection=kotlin-code \
  --qdrant-url=http://localhost:6333 \
  --batch-size=50
```

### 5. Set Up Code Generation

```bash
# Install Python dependencies
cd code-gen
pip install -r requirements.txt

# Configure your Claude API key in config.yaml
# Update the api_key field with your actual key
```

### 6. Start AI-Powered Code Generation

```bash
# Interactive code generation
python claude_rag.py
```

Example interaction:
```
What would you like help with?
> How do I create a REST API endpoint that validates user input?

--- Planner Output ---
1. How to create a REST API endpoint structure?
2. What are the common patterns for input validation?
3. How to handle validation errors properly?
4. What libraries are commonly used for validation?

Processing sub-question: How to create a REST API endpoint structure?
Processing sub-question: What are the common patterns for input validation?
Processing sub-question: How to handle validation errors properly?
Processing sub-question: What libraries are commonly used for validation?

--- Final Answer ---
[Generated code and explanations based on your indexed codebase]
```

## Usage Examples

### Complete RAG Pipeline

```bash
# 1. Start Qdrant
docker run -d --name qdrant -p 6333:6333 qdrant/qdrant

# 2. Start embedding service (in another terminal)
uvicorn embedding_service:app --host 0.0.0.0 --port 8000

# 3. Build tools
./gradlew build

# 4. Parse and import code
java -jar ast-parser/build/libs/ast-parser-1.0-SNAPSHOT.jar \
  --output=jsonl \
  src/ | \
java -jar qdrant-import/build/libs/qdrant-import-1.0-SNAPSHOT.jar \
  --collection=kotlin-code \
  --batch-size=25

# 5. Start code generation (in another terminal)
cd code-gen
python claude_rag.py
```

### Ask Questions About Your Code

```
What would you like help with?
> Show me how to implement pagination in a REST API

> How do I handle database transactions safely?

> What's the pattern for input validation with custom annotations?

> Generate a service class that follows our team's conventions
```

### With Custom Embedding Service

If you have an embedding service running:

```bash
cat code_chunks.jsonl | java -jar qdrant-import/build/libs/qdrant-import-1.0-SNAPSHOT.jar \
  --collection=kotlin-code \
  --embedding-url=http://localhost:8000 \
  --qdrant-url=http://localhost:6333
```

The embedding service should accept POST requests to `/embed` with:
```json
{"texts": ["code text here"]}
```

And return:
```json
{"embeddings": [[0.1, 0.2, 0.3, ...]]}
```

**Note**: If no embedding service is provided, the qdrant-import tool will fall back to generating random vectors for testing purposes.

### Development and Testing

```bash
# Build individual modules
./gradlew :ast-parser:build
./gradlew :qdrant-import:build

# Test with sample output
java -jar ast-parser/build/libs/ast-parser-1.0-SNAPSHOT.jar \
  --output=summary \
  ast-parser/src/

# View JSONL output
java -jar ast-parser/build/libs/ast-parser-1.0-SNAPSHOT.jar \
  --output=jsonl \
  ast-parser/src/ | head -5
```

## Configuration Options

### ast-parser Options

- `--output=jsonl|json|summary` - Output format (default: summary)
- Files and directories can be mixed in arguments
- Recursively processes directories for `.kt` and `.kts` files

### qdrant-import Options

- `--qdrant-url` - Qdrant server URL (default: http://localhost:6333)
- `--collection` - Collection name (required)
- `--batch-size` - Upload batch size (default: 100)
- `--embedding-url` - Embedding service URL (default: http://localhost:8000)

### code-gen Configuration (config.yaml)

```yaml
llm:
  provider: anthropic
  model: claude-3-7-sonnet-20250219  # Or claude-3-5-sonnet-20241022
  temperature: 0.2
  api_key: "your-claude-api-key-here"

qdrant:
  host: localhost
  port: 6333
  collection_name: kotlin-code

retriever:
  top_k: 10  # Number of code examples to retrieve

embedding:
  model: BAAI/bge-small-en-v1.5  # HuggingFace embedding model
```

## Output Formats

### JSONL (for Qdrant)
```json
{"id":"uuid","file_path":"/path/file.kt","symbol":"MyClass.myFunction","kind":"function","code":"fun myFunction() {...}","metadata":{"modifiers":[],"annotations":[],"parent":"MyClass"}}
```

### JSON (structured)
```json
{
  "file_path": "/path/file.kt",
  "declarations": [
    {
      "id": "uuid",
      "symbol": "MyClass.myFunction",
      "kind": "function",
      "code": "fun myFunction() {...}",
      "metadata": {...}
    }
  ]
}
```

### Summary (human-readable)
```
Processing 15 Kotlin files...

=== Processing: /path/file.kt ===
Found 3 declarations:
  - class: MyClass
  - function: MyClass.myFunction
  - function: MyClass.anotherFunction
```

## Use Cases

- **AI-Powered Code Generation**: Ask questions and get code suggestions based on your existing codebase
- **Code Search**: Find similar functions across large codebases using semantic search
- **Team Knowledge Base**: Create an AI assistant that understands your team's coding patterns
- **Code Documentation**: Generate context-aware documentation and examples
- **Onboarding**: Help new team members understand existing code patterns and conventions
- **Refactoring**: Identify duplicate patterns and get suggestions for improvements
- **Learning**: Explore how certain patterns are implemented across your projects

## Extending the Tools

All tools are designed to be extensible:

- **ast-parser**: Add new AST node types or output formats
- **qdrant-import**: Integrate different embedding models or vector databases
- **code-gen**: Customize prompts, add new agents, or integrate other LLMs
- **Library Usage**: Import as Gradle modules in other projects

### Adding Custom Prompts

Modify `claude_rag.py` to add specialized prompts:

```python
# Add domain-specific prompts
security_prompt = PromptTemplate.from_template("""
You are a security-focused Kotlin engineer. Analyze this code for security vulnerabilities:

Context: {context}
Question: {question}

Focus on: authentication, authorization, input validation, and data exposure.
""")
```

## Troubleshooting

### Common Issues

1. **Qdrant Connection Errors**: Ensure Qdrant is running on the correct port
2. **Out of Memory**: Reduce batch size for large codebases
3. **Parsing Errors**: Check Kotlin file syntax and encoding
4. **Empty Results**: Verify file extensions and permissions
5. **Claude API Errors**: Check your API key and rate limits
6. **Poor Retrieval Results**: Ensure embeddings are generated correctly and collection has data
7. **Python Dependencies**: Use `pip install -r code-gen/requirements.txt`

### Debugging

```bash
# Check Qdrant status
curl http://localhost:6333/health

# Verify collection exists and has data
curl http://localhost:6333/collections/kotlin-code

# Test with small dataset first
head -10 code_chunks.jsonl | java -jar qdrant-import/build/libs/qdrant-import-1.0-SNAPSHOT.jar --collection=test

# Test embedding service
curl -X POST http://localhost:8000/embed \
  -H "Content-Type: application/json" \
  -d '{"texts": ["fun test() { println(\"hello\") }"]}'

# Test Claude API (from code-gen directory)
python -c "
import yaml
from langchain_anthropic import ChatAnthropic

with open('config.yaml') as f:
    config = yaml.safe_load(f)

llm = ChatAnthropic(model=config['llm']['model'], api_key=config['llm']['api_key'])
print(llm.invoke('Hello').content)
"

# Check vector count in collection
curl http://localhost:6333/collections/kotlin-code/points/count
```