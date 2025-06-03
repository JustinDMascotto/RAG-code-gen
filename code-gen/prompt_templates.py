"""Prompt templates for the RAG system."""

from langchain.prompts import PromptTemplate, ChatPromptTemplate


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


# Synthesis prompt for combining answers
synthesis_prompt = PromptTemplate.from_template("""
Synthesize these project-specific answers into one comprehensive solution:

PROJECT CONTEXT:
{project_context}

SUB-ANSWERS:
{subanswers}

Provide a clear, actionable solution that follows the project's patterns and conventions.
""")


class PromptManager:
    """Manages prompt templates for the RAG system."""
    
    def __init__(self):
        """Initialize prompt manager with all templates."""
        self.context_aware_prompt = context_aware_prompt
        self.file_operation_prompt = file_operation_prompt
        self.planner_prompt = planner_prompt
        self.synthesis_prompt = synthesis_prompt
    
    def get_context_aware_prompt(self) -> PromptTemplate:
        """Get the context-aware prompt template."""
        return self.context_aware_prompt
    
    def get_file_operation_prompt(self) -> PromptTemplate:
        """Get the file operation prompt template."""
        return self.file_operation_prompt
    
    def get_planner_prompt(self) -> ChatPromptTemplate:
        """Get the planner prompt template."""
        return self.planner_prompt
    
    def get_synthesis_prompt(self) -> PromptTemplate:
        """Get the synthesis prompt template."""
        return self.synthesis_prompt