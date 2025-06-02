import os
import json
from pathlib import Path
from typing import Dict, List, Optional, Set
import fnmatch

class ProjectContext:
    """Provides context about the current project structure and conventions."""
    
    def __init__(self, root_path: str = "."):
        self.root_path = Path(root_path).resolve()
        self.ignore_patterns = self._get_ignore_patterns()
        
    def _get_ignore_patterns(self) -> Set[str]:
        """Load ignore patterns from .gitignore and common build directories."""
        patterns = {
            ".git", ".gradle", "build", "target", ".idea", ".vscode",
            "node_modules", "__pycache__", "*.class", "*.jar", "*.log", "venv"
        }
        
        gitignore_path = self.root_path / ".gitignore"
        if gitignore_path.exists():
            with open(gitignore_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        patterns.add(line)
        
        return patterns
    
    def _should_ignore(self, path: Path) -> bool:
        """Check if a path should be ignored based on patterns."""
        relative_path = path.relative_to(self.root_path)
        
        for pattern in self.ignore_patterns:
            if fnmatch.fnmatch(str(relative_path), pattern):
                return True
            if fnmatch.fnmatch(path.name, pattern):
                return True
        
        return False
    
    def scan_project_structure(self) -> Dict:
        """Scan and analyze the project structure."""
        structure = {
            "root": str(self.root_path),
            "directories": [],
            "kotlin_files": [],
            "other_files": [],
            "build_files": [],
            "patterns": {
                "package_structure": self._analyze_package_structure(),
                "naming_conventions": self._analyze_naming_conventions(),
                "common_patterns": self._detect_common_patterns()
            }
        }
        
        for root, dirs, files in os.walk(self.root_path):
            root_path = Path(root)
            
            # Filter out ignored directories
            dirs[:] = [d for d in dirs if not self._should_ignore(root_path / d)]
            
            if self._should_ignore(root_path):
                continue
                
            # Analyze directories
            relative_root = root_path.relative_to(self.root_path)
            if relative_root != Path("."):
                structure["directories"].append(str(relative_root))
            
            # Analyze files
            for file in files:
                file_path = root_path / file
                if self._should_ignore(file_path):
                    continue
                    
                relative_file = file_path.relative_to(self.root_path)
                
                if file.endswith(('.kt', '.kts')):
                    structure["kotlin_files"].append({
                        "path": str(relative_file),
                        "package": self._extract_package(file_path),
                        "classes": self._extract_class_names(file_path)
                    })
                elif file in ('build.gradle', 'build.gradle.kts', 'pom.xml', 'settings.gradle.kts'):
                    structure["build_files"].append(str(relative_file))
                else:
                    structure["other_files"].append(str(relative_file))
        
        return structure
    
    def _extract_package(self, file_path: Path) -> Optional[str]:
        """Extract package declaration from Kotlin file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('package '):
                        return line.replace('package ', '').strip().rstrip(';')
                    if line and not line.startswith('//') and not line.startswith('/*'):
                        break  # Stop at first non-comment, non-package line
        except Exception:
            pass
        return None
    
    def _extract_class_names(self, file_path: Path) -> List[str]:
        """Extract class/object/interface names from Kotlin file."""
        classes = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Simple regex-like parsing for class declarations
            import re
            patterns = [
                r'class\s+(\w+)',
                r'object\s+(\w+)',
                r'interface\s+(\w+)',
                r'data class\s+(\w+)',
                r'sealed class\s+(\w+)',
                r'enum class\s+(\w+)'
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, content)
                classes.extend(matches)
        except Exception:
            pass
        return classes
    
    def _analyze_package_structure(self) -> Dict:
        """Analyze package naming patterns."""
        packages = set()
        
        for root, dirs, files in os.walk(self.root_path):
            for file in files:
                if file.endswith(('.kt', '.kts')):
                    file_path = Path(root) / file
                    if not self._should_ignore(file_path):
                        package = self._extract_package(file_path)
                        if package:
                            packages.add(package)
        
        if not packages:
            return {}
            
        # Find common package root
        package_list = list(packages)
        if len(package_list) == 1:
            common_root = package_list[0]
        else:
            common_parts = []
            first_package_parts = package_list[0].split('.')
            
            for i, part in enumerate(first_package_parts):
                if all(pkg.split('.')[i:i+1] == [part] for pkg in package_list if len(pkg.split('.')) > i):
                    common_parts.append(part)
                else:
                    break
            
            common_root = '.'.join(common_parts) if common_parts else ""
        
        return {
            "common_root": common_root,
            "all_packages": sorted(list(packages)),
            "package_count": len(packages)
        }
    
    def _analyze_naming_conventions(self) -> Dict:
        """Analyze naming conventions used in the project."""
        conventions = {
            "file_naming": "PascalCase",  # Default assumption
            "class_naming": "PascalCase",
            "common_suffixes": set(),
            "common_prefixes": set()
        }
        
        class_names = []
        file_names = []
        
        for root, dirs, files in os.walk(self.root_path):
            for file in files:
                if file.endswith('.kt'):
                    file_path = Path(root) / file
                    if not self._should_ignore(file_path):
                        # Analyze file naming
                        file_name = Path(file).stem
                        file_names.append(file_name)
                        
                        # Analyze class naming
                        classes = self._extract_class_names(file_path)
                        class_names.extend(classes)
        
        # Analyze common suffixes/prefixes
        common_suffixes = ['Service', 'Controller', 'Repository', 'Dao', 'Dto', 'Entity', 'Config', 'Exception', 'Test']
        common_prefixes = ['Abstract', 'Base', 'Default', 'Mock', 'Test']
        
        for name in class_names + file_names:
            # Check suffixes
            for suffix in common_suffixes:
                if name.endswith(suffix):
                    conventions["common_suffixes"].add(suffix)
                    break
            
            # Check prefixes
            for prefix in common_prefixes:
                if name.startswith(prefix):
                    conventions["common_prefixes"].add(prefix)
                    break
        
        conventions["common_suffixes"] = list(conventions["common_suffixes"])
        conventions["common_prefixes"] = list(conventions["common_prefixes"])
        
        return conventions
    
    def _detect_common_patterns(self) -> Dict:
        """Detect common architectural patterns in the project."""
        patterns = {
            "has_gradle": False,
            "has_maven": False,
            "architecture_patterns": [],
            "dependency_injection": False,
            "test_structure": []
        }
        
        # Check build system
        if (self.root_path / "build.gradle").exists() or (self.root_path / "build.gradle.kts").exists():
            patterns["has_gradle"] = True
        if (self.root_path / "pom.xml").exists():
            patterns["has_maven"] = True
        
        # Check for common architectural patterns
        dir_names = []
        for root, dirs, files in os.walk(self.root_path):
            dir_names.extend(dirs)
        
        if any('controller' in d.lower() for d in dir_names):
            patterns["architecture_patterns"].append("MVC")
        if any('service' in d.lower() for d in dir_names):
            patterns["architecture_patterns"].append("Service Layer")
        if any('repository' in d.lower() or 'dao' in d.lower() for d in dir_names):
            patterns["architecture_patterns"].append("Repository Pattern")
        
        # Check test structure
        test_dirs = [d for d in dir_names if 'test' in d.lower()]
        patterns["test_structure"] = test_dirs
        
        return patterns
    
    def get_suggested_file_location(self, class_name: str, class_type: str = "class") -> str:
        """Suggest where a new file should be placed based on project patterns."""
        structure = self.scan_project_structure()
        package_info = structure["patterns"]["package_structure"]
        
        # Default to main source directory
        base_path = "src/main/kotlin"
        
        # Use common package root if available
        if package_info.get("common_root"):
            package_path = package_info["common_root"].replace('.', '/')
            suggested_path = f"{base_path}/{package_path}"
        else:
            suggested_path = base_path
        
        # Add type-specific subdirectory based on detected patterns
        if class_type.lower() in ['controller', 'rest']:
            suggested_path += "/controller"
        elif class_type.lower() in ['service']:
            suggested_path += "/service"
        elif class_type.lower() in ['repository', 'dao']:
            suggested_path += "/repository"
        elif class_type.lower() in ['entity', 'model']:
            suggested_path += "/model"
        
        return f"{suggested_path}/{class_name}.kt"
    
    def to_context_string(self, max_length: int = 2000) -> str:
        """Generate a context string for LLM prompts with length limits."""
        structure = self.scan_project_structure()
        
        # Start with essential info
        context = f"""Project Context:
- Root: {Path(structure['root']).name}
- Package: {structure['patterns']['package_structure'].get('common_root', 'No common package')}
- Architecture: {', '.join(structure['patterns']['common_patterns']['architecture_patterns']) or 'Standard'}
- Build: {'Gradle' if structure['patterns']['common_patterns']['has_gradle'] else 'Maven' if structure['patterns']['common_patterns']['has_maven'] else 'Unknown'}"""
        
        # Add directories (limited)
        dirs = structure['directories'][:5]
        if dirs:
            context += f"\n\nKey Directories:\n" + "\n".join(f"  - {d}" for d in dirs)
            if len(structure['directories']) > 5:
                context += f"\n  ... and {len(structure['directories']) - 5} more"
        
        # Add recent Kotlin files (limited)
        kotlin_files = structure['kotlin_files'][:5]
        if kotlin_files:
            context += f"\n\nRecent Kotlin Files:\n" + "\n".join(f"  - {f['path']}" for f in kotlin_files)
            if len(structure['kotlin_files']) > 5:
                context += f"\n  ... and {len(structure['kotlin_files']) - 5} more"
        
        # Add conventions
        suffixes = structure['patterns']['naming_conventions']['common_suffixes'][:3]
        if suffixes:
            context += f"\n\nConventions: {', '.join(suffixes)}"
        
        # Truncate if too long
        if len(context) > max_length:
            context = context[:max_length-3] + "..."
        
        return context
    
    def get_focused_context(self, query: str, max_length: int = 1500) -> str:
        """Get context focused on the query with strict length limits."""
        structure = self.scan_project_structure()
        
        # Essential info only
        context = f"""Project: {Path(structure['root']).name}
Package: {structure['patterns']['package_structure'].get('common_root', 'none')}
Build: {'Gradle' if structure['patterns']['common_patterns']['has_gradle'] else 'Maven'}"""
        
        # Query-specific filtering
        query_lower = query.lower()
        
        # If asking about specific file types
        if any(term in query_lower for term in ['controller', 'service', 'repository', 'test']):
            relevant_files = [
                f for f in structure['kotlin_files'][:10] 
                if any(term in f['path'].lower() for term in ['controller', 'service', 'repository', 'test'])
            ]
            if relevant_files:
                context += f"\n\nRelevant Files:\n" + "\n".join(f"  - {f['path']}" for f in relevant_files[:3])
        
        # Truncate strictly
        if len(context) > max_length:
            context = context[:max_length-3] + "..."
        
        return context