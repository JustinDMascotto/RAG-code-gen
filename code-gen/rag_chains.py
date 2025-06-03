"""RAG chain implementations for the enhanced Claude RAG system."""

import json
from typing import Dict, List, Any
from langchain_core.runnables import RunnableMap
from prompt_templates import PromptManager
from llm_manager import LLMManager
from retrieval_manager import RetrievalManager
from project_context import ProjectContext
from file_operations import FileOperations


class RAGChains:
    """Manages RAG processing chains and workflows."""
    
    def __init__(self, 
                 llm_manager: LLMManager,
                 retrieval_manager: RetrievalManager, 
                 project_context: ProjectContext,
                 file_ops: FileOperations):
        """Initialize RAG chains with required managers."""
        self.llm_manager = llm_manager
        self.retrieval_manager = retrieval_manager
        self.project_context = project_context
        self.file_ops = file_ops
        self.prompt_manager = PromptManager()
        
        # Initialize chains
        self._setup_chains()
    
    def _setup_chains(self):
        """Setup all processing chains."""
        llm = self.llm_manager.get_llm()
        
        # Planner chain
        self.planner_chain = self.prompt_manager.get_planner_prompt() | llm
        
        # Context-aware chain
        self.context_aware_chain = RunnableMap({
            "project_context": lambda x: self.project_context.get_focused_context(x["question"], 2000),
            "retrieved_code": lambda x: self.retrieval_manager.truncate_retrieved_content(
                self.retrieval_manager.cached_retrieve(x["question"]), 5000
            ),
            "question": lambda x: x["question"]
        }) | self.prompt_manager.get_context_aware_prompt() | llm
        
        # File operation chain
        self.file_operation_chain = RunnableMap({
            "project_context": lambda x: self.project_context.get_focused_context(x["question"], 800),
            "retrieved_code": lambda x: self.retrieval_manager.truncate_retrieved_content(
                self.retrieval_manager.cached_retrieve(x["question"]), 2000
            ),
            "question": lambda x: x["question"],
            "current_file_content": lambda x: x.get("current_file_content", "")[:1000] + 
                ("..." if len(x.get("current_file_content", "")) > 1000 else "")
        }) | self.prompt_manager.get_file_operation_prompt() | llm
        
        # Synthesis chain
        self.synthesis_chain = self.prompt_manager.get_synthesis_prompt() | llm
    
    def execute_file_operations(self, operations_json: str) -> List[str]:
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
                    success, message = self.file_ops.create_file(path, content)
                    results.append(f"Create {path}: {message}")
                    
                elif op_type == "modify_file":
                    modifications = op.get("modifications", [])
                    success, message = self.file_ops.modify_file(path, modifications)
                    results.append(f"Modify {path}: {message}")
                    
                elif op_type == "create_directory":
                    success, message = self.file_ops.create_directory(path)
                    results.append(f"Create directory {path}: {message}")
                    
        except json.JSONDecodeError as e:
            results.append(f"Error parsing operations JSON: {e}")
        except Exception as e:
            results.append(f"Error executing operations: {e}")
        
        return results
    
    def run_file_operation_workflow(self, question: str, execute_operations: bool = False) -> str:
        """Run the file operation workflow."""
        print("🔧 Planning file operations...")
        
        # Get current file content if modifying
        current_file_content = ""
        if "modify" in question.lower() or "update" in question.lower():
            print("Note: If modifying an existing file, specify the file path")
        
        # Generate file operations
        response = self.llm_manager.invoke_with_retry(self.file_operation_chain, {
            "question": question,
            "current_file_content": current_file_content
        })
        
        # Parse and execute operations
        operations_json = response.content.strip()
        print(f"\n📋 Planned Operations:\n{operations_json}")
        
        if execute_operations:
            # Confirm before executing
            confirm = input("\n⚠️  Execute these operations? (y/N): ").lower().strip()
            if confirm == 'y':
                results = self.execute_file_operations(operations_json)
                print(f"\n✅ Execution Results:")
                for result in results:
                    print(f"  {result}")
            else:
                print("Operations cancelled.")
        
        return operations_json
    
    def run_context_aware_workflow(self, question: str) -> str:
        """Run the context-aware RAG workflow."""
        print("🔍 Analyzing project and retrieving relevant code...")
        
        # Step 1: Plan the approach
        plan_response = self.llm_manager.invoke_with_retry(self.planner_chain, {
            "question": question,
            "project_context": self.project_context.get_focused_context(question, 800)
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
            result = self.llm_manager.invoke_with_retry(
                self.context_aware_chain, 
                {"question": sub}
            )
            answers.append((sub, result.content.strip()))
        
        # Step 4: Synthesize final answer
        if len(answers) > 1:
            subanswer_text = "\n\n".join(f"Q: {q}\nA: {a}" for q, a in answers)
            
            # Truncate subanswers if too long
            max_subanswer_length = 4000
            if len(subanswer_text) > max_subanswer_length:
                subanswer_text = subanswer_text[:max_subanswer_length] + "\n\n[Additional answers truncated...]"
            
            final_response = self.llm_manager.invoke_with_retry(self.synthesis_chain, {
                "project_context": self.project_context.get_focused_context(question, 600),
                "subanswers": subanswer_text
            })
            
            return final_response.content
        else:
            return answers[0][1] if answers else "No relevant information found."