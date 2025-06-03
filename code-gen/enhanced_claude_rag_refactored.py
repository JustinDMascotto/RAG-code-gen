#!/usr/bin/env python3
"""
Enhanced RAG Code Assistant with project awareness - Refactored version.

This is the main entry point for the refactored enhanced Claude RAG system.
The original large file has been broken down into focused modules.
"""

import argparse
import sys
from pathlib import Path

# Import our modular components
from config_manager import load_config
from llm_manager import LLMManager
from retrieval_manager import RetrievalManager
from rag_chains import RAGChains
from cli_interface import CLIInterface
from project_context import ProjectContext
from file_operations import FileOperations


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Enhanced RAG Code Assistant with project awareness",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python enhanced_claude_rag_refactored.py
  python enhanced_claude_rag_refactored.py --config /path/to/my-config.yaml
  python enhanced_claude_rag_refactored.py -c production.yaml
  python enhanced_claude_rag_refactored.py --config ../configs/team-config.yaml
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
        version="Enhanced RAG Code Assistant 2.0 (Refactored)"
    )
    
    return parser.parse_args()


def main():
    """Main entry point for the enhanced RAG system."""
    # Parse command line arguments
    args = parse_arguments()
    
    try:
        # Load configuration
        config = load_config(args.config)
        
        # Initialize managers
        llm_manager = LLMManager(config)
        retrieval_manager = RetrievalManager(config)
        
        # Initialize project context and file operations
        project_context = ProjectContext(args.project_root)
        file_ops = FileOperations(args.project_root)
        
        # Initialize RAG processing chains
        rag_chains = RAGChains(
            llm_manager=llm_manager,
            retrieval_manager=retrieval_manager,
            project_context=project_context,
            file_ops=file_ops
        )
        
        # Initialize and run CLI interface
        cli = CLIInterface(
            rag_chains=rag_chains,
            project_context=project_context,
            file_ops=file_ops,
            config=config,
            config_path=args.config
        )
        
        cli.run()
        
    except KeyboardInterrupt:
        print("\n\nGoodbye! 👋")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()