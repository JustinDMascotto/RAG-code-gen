"""Command-line interface for the enhanced RAG system."""

import json
from pathlib import Path
from typing import Dict, Any
from rag_chains import RAGChains
from project_context import ProjectContext
from file_operations import FileOperations


class CLIInterface:
    """Command-line interface for the enhanced RAG system."""
    
    def __init__(self, 
                 rag_chains: RAGChains,
                 project_context: ProjectContext,
                 file_ops: FileOperations,
                 config: Dict[str, Any],
                 config_path: str):
        """Initialize CLI interface."""
        self.rag_chains = rag_chains
        self.project_context = project_context
        self.file_ops = file_ops
        self.config = config
        self.config_path = config_path
    
    def show_startup_info(self):
        """Show startup information."""
        print("🚀 Enhanced RAG Code Assistant")
        print("=" * 50)
        print(f"📁 Project: {self.project_context.root_path}")
        print(f"⚙️  Config: {Path(self.config_path).absolute()}")
        print(f"🤖 Model: {self.config['llm']['model']}")
        
        # Show project context
        structure = self.project_context.scan_project_structure()
        print(f"📦 Package: {structure['patterns']['package_structure'].get('common_root', 'None')}")
        print(f"🏗️  Architecture: {', '.join(structure['patterns']['common_patterns']['architecture_patterns']) or 'Standard'}")
        print(f"📝 Kotlin files: {len(structure['kotlin_files'])}")
        print(f"📂 Directories: {len(structure['directories'])}")
        
        print("\nType 'exit' to quit, 'help' for commands")
        print("Add '--execute' to your question to perform file operations")
        print("-" * 50)
    
    def show_help(self):
        """Show help information."""
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
    
    def handle_backups_command(self):
        """Handle the backups command."""
        backups = self.file_ops.list_backups()
        if backups:
            print(f"\n📁 Available backups ({len(backups)}):")
            for backup in backups[:10]:
                print(f"  {backup['name']} ({backup['size']} bytes, {backup['created']})")
        else:
            print("No backups found.")
    
    def handle_context_command(self):
        """Handle the context command."""
        print(f"\n{self.project_context.to_context_string()}")
    
    def handle_structure_command(self):
        """Handle the structure command."""
        structure = self.project_context.scan_project_structure()
        print(f"\n📊 Project Structure:")
        print(json.dumps(structure, indent=2, default=str))
    
    def handle_status_command(self):
        """Handle the status command."""
        print("\n🔍 Checking API connectivity...")
        try:
            # Test Claude API
            llm = self.rag_chains.llm_manager.get_llm()
            test_response = self.rag_chains.llm_manager.invoke_with_retry(
                llm, {"messages": [{"role": "user", "content": "Hello"}]}
            )
            print("✅ Claude API: Connected")
            
            # Test Qdrant
            qdrant_info = self.rag_chains.retrieval_manager.get_collection_info()
            if qdrant_info["status"] == "connected":
                print(f"✅ Qdrant: Connected ({qdrant_info['vector_count']} vectors in '{self.config['qdrant']['collection_name']}')")
            else:
                print(f"❌ Qdrant: Connection failed - {qdrant_info['error']}")
                
        except Exception as e:
            print(f"❌ Claude API: Connection failed - {e}")
    
    def is_file_operation_request(self, question: str) -> bool:
        """Check if the question is a file operation request."""
        file_operation_keywords = [
            "create", "generate", "add", "implement", "build", "make",
            "file", "class", "service", "controller", "repository",
            "modify", "update", "change", "fix", "refactor"
        ]
        return any(keyword in question.lower() for keyword in file_operation_keywords)
    
    def process_question(self, question: str, execute_ops: bool = False) -> str:
        """Process a user question and return the response."""
        if self.is_file_operation_request(question) and execute_ops:
            return self.rag_chains.run_file_operation_workflow(question, execute_operations=True)
        else:
            return self.rag_chains.run_context_aware_workflow(question)
    
    def run(self):
        """Run the interactive CLI."""
        self.show_startup_info()
        
        while True:
            try:
                question = input("\n💭 What would you like help with?\n> ").strip()
                
                if not question:
                    continue
                    
                if question.lower() == 'exit':
                    break
                    
                if question.lower() == 'help':
                    self.show_help()
                    continue
                    
                if question.lower() == 'backups':
                    self.handle_backups_command()
                    continue
                    
                if question.lower() == 'context':
                    self.handle_context_command()
                    continue
                    
                if question.lower() == 'structure':
                    self.handle_structure_command()
                    continue
                    
                if question.lower() == 'status':
                    self.handle_status_command()
                    continue
                
                execute_ops = '--execute' in question
                if execute_ops:
                    question = question.replace('--execute', '').strip()
                
                print(f"\n🤖 Processing: {question}")
                response = self.process_question(question, execute_ops)
                
                print(f"\n💡 Response:")
                print(response)
                
            except KeyboardInterrupt:
                print("\n\nGoodbye! 👋")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}")