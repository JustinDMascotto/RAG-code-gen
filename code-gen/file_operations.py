import os
import json
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import difflib

class FileOperations:
    """Handles safe file creation and modification operations."""
    
    def __init__(self, root_path: str = ".", backup_dir: str = ".code-gen-backups"):
        self.root_path = Path(root_path).resolve()
        self.backup_dir = self.root_path / backup_dir
        self.backup_dir.mkdir(exist_ok=True)
        
        # Safety settings
        self.max_file_size = 1024 * 1024  # 1MB max file size
        self.allowed_extensions = {'.kt', '.kts', '.java', '.gradle', '.md', '.txt', '.yaml', '.yml', '.json'}
        self.protected_files = {'build.gradle', 'settings.gradle', 'gradle.properties', '.gitignore'}
        
    def _is_safe_operation(self, file_path: Path, operation: str) -> Tuple[bool, str]:
        """Check if a file operation is safe to perform."""
        try:
            # Resolve the path to prevent directory traversal
            resolved_path = file_path.resolve()
            
            # Ensure the file is within the project root
            if not str(resolved_path).startswith(str(self.root_path)):
                return False, f"File {file_path} is outside project root"
            
            # Check file extension
            if file_path.suffix not in self.allowed_extensions:
                return False, f"File extension {file_path.suffix} not allowed"
            
            # Check protected files for modification
            if operation in ['modify', 'delete'] and file_path.name in self.protected_files:
                return False, f"File {file_path.name} is protected from {operation}"
            
            # Check file size for existing files
            if file_path.exists() and file_path.stat().st_size > self.max_file_size:
                return False, f"File {file_path} exceeds maximum size limit"
            
            return True, "Safe operation"
            
        except Exception as e:
            return False, f"Error checking file safety: {str(e)}"
    
    def _create_backup(self, file_path: Path) -> Optional[Path]:
        """Create a backup of an existing file."""
        if not file_path.exists():
            return None
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{file_path.stem}_{timestamp}{file_path.suffix}"
        backup_path = self.backup_dir / backup_name
        
        try:
            shutil.copy2(file_path, backup_path)
            return backup_path
        except Exception as e:
            print(f"Warning: Could not create backup for {file_path}: {e}")
            return None
    
    def create_file(self, file_path: str, content: str, overwrite: bool = False) -> Tuple[bool, str]:
        """Create a new file with the given content."""
        path = Path(file_path)
        if not path.is_absolute():
            path = self.root_path / path
        
        # Safety check
        safe, message = self._is_safe_operation(path, 'create')
        if not safe:
            return False, message
        
        # Check if file exists
        if path.exists() and not overwrite:
            return False, f"File {path} already exists. Use overwrite=True to replace."
        
        try:
            # Create parent directories if they don't exist
            path.parent.mkdir(parents=True, exist_ok=True)
            
            # Create backup if file exists
            if path.exists():
                backup_path = self._create_backup(path)
                if backup_path:
                    print(f"Created backup: {backup_path}")
            
            # Write the file
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            return True, f"Successfully created {path}"
            
        except Exception as e:
            return False, f"Error creating file {path}: {str(e)}"
    
    def modify_file(self, file_path: str, modifications: List[Dict]) -> Tuple[bool, str]:
        """
        Modify an existing file with specific changes.
        
        modifications: List of dictionaries with keys:
        - type: 'replace', 'insert_at_line', 'append', 'prepend'
        - old_text: text to replace (for 'replace' type)
        - new_text: new text to insert
        - line_number: line number for 'insert_at_line' type
        """
        path = Path(file_path)
        if not path.is_absolute():
            path = self.root_path / path
        
        # Safety check
        safe, message = self._is_safe_operation(path, 'modify')
        if not safe:
            return False, message
        
        if not path.exists():
            return False, f"File {path} does not exist"
        
        try:
            # Read current content
            with open(path, 'r', encoding='utf-8') as f:
                original_content = f.read()
            
            lines = original_content.splitlines()
            modified_content = original_content
            
            # Create backup
            backup_path = self._create_backup(path)
            if backup_path:
                print(f"Created backup: {backup_path}")
            
            # Apply modifications
            for mod in modifications:
                mod_type = mod.get('type', '')
                
                if mod_type == 'replace':
                    old_text = mod.get('old_text', '')
                    new_text = mod.get('new_text', '')
                    if old_text in modified_content:
                        modified_content = modified_content.replace(old_text, new_text)
                    else:
                        return False, f"Text to replace not found: {old_text[:50]}..."
                
                elif mod_type == 'insert_at_line':
                    line_num = mod.get('line_number', 1) - 1  # Convert to 0-based
                    new_text = mod.get('new_text', '')
                    lines = modified_content.splitlines()
                    if 0 <= line_num <= len(lines):
                        lines.insert(line_num, new_text)
                        modified_content = '\n'.join(lines)
                    else:
                        return False, f"Invalid line number: {line_num + 1}"
                
                elif mod_type == 'append':
                    new_text = mod.get('new_text', '')
                    modified_content += '\n' + new_text
                
                elif mod_type == 'prepend':
                    new_text = mod.get('new_text', '')
                    modified_content = new_text + '\n' + modified_content
                
                else:
                    return False, f"Unknown modification type: {mod_type}"
            
            # Write modified content
            with open(path, 'w', encoding='utf-8') as f:
                f.write(modified_content)
            
            # Generate diff for review
            diff = self._generate_diff(original_content, modified_content, str(path))
            print(f"Applied modifications to {path}")
            print("Changes made:")
            print(diff)
            
            return True, f"Successfully modified {path}"
            
        except Exception as e:
            return False, f"Error modifying file {path}: {str(e)}"
    
    def _generate_diff(self, original: str, modified: str, filename: str) -> str:
        """Generate a readable diff between original and modified content."""
        original_lines = original.splitlines(keepends=True)
        modified_lines = modified.splitlines(keepends=True)
        
        diff = difflib.unified_diff(
            original_lines,
            modified_lines,
            fromfile=f"{filename} (original)",
            tofile=f"{filename} (modified)",
            n=3
        )
        
        return ''.join(diff)
    
    def create_directory(self, dir_path: str) -> Tuple[bool, str]:
        """Create a directory structure."""
        path = Path(dir_path)
        if not path.is_absolute():
            path = self.root_path / path
        
        try:
            # Ensure directory is within project root
            if not str(path.resolve()).startswith(str(self.root_path)):
                return False, f"Directory {path} is outside project root"
            
            path.mkdir(parents=True, exist_ok=True)
            return True, f"Successfully created directory {path}"
            
        except Exception as e:
            return False, f"Error creating directory {path}: {str(e)}"
    
    def list_backups(self) -> List[Dict]:
        """List all available backups."""
        backups = []
        
        if not self.backup_dir.exists():
            return backups
        
        for backup_file in self.backup_dir.iterdir():
            if backup_file.is_file():
                try:
                    stat = backup_file.stat()
                    backups.append({
                        'name': backup_file.name,
                        'path': str(backup_file),
                        'size': stat.st_size,
                        'created': datetime.fromtimestamp(stat.st_ctime).isoformat(),
                        'modified': datetime.fromtimestamp(stat.st_mtime).isoformat()
                    })
                except Exception:
                    continue
        
        return sorted(backups, key=lambda x: x['created'], reverse=True)
    
    def restore_backup(self, backup_name: str, target_path: str) -> Tuple[bool, str]:
        """Restore a file from backup."""
        backup_path = self.backup_dir / backup_name
        target = Path(target_path)
        
        if not target.is_absolute():
            target = self.root_path / target
        
        if not backup_path.exists():
            return False, f"Backup {backup_name} not found"
        
        # Safety check for target
        safe, message = self._is_safe_operation(target, 'create')
        if not safe:
            return False, message
        
        try:
            shutil.copy2(backup_path, target)
            return True, f"Successfully restored {backup_name} to {target}"
        except Exception as e:
            return False, f"Error restoring backup: {str(e)}"
    
    def preview_file_operation(self, operation: str, file_path: str, content: str = None) -> str:
        """Preview what a file operation would do without executing it."""
        path = Path(file_path)
        if not path.is_absolute():
            path = self.root_path / path
        
        preview = f"Operation: {operation}\n"
        preview += f"Target: {path}\n"
        preview += f"Exists: {path.exists()}\n"
        
        if path.exists():
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    current_content = f.read()
                preview += f"Current size: {len(current_content)} characters\n"
                
                if content and operation in ['create', 'modify']:
                    diff = self._generate_diff(current_content, content, str(path))
                    preview += f"Proposed changes:\n{diff}\n"
            except Exception as e:
                preview += f"Error reading current file: {e}\n"
        
        elif content and operation == 'create':
            preview += f"New file size: {len(content)} characters\n"
            preview += f"First 200 characters:\n{content[:200]}...\n" if len(content) > 200 else f"Content:\n{content}\n"
        
        safe, message = self._is_safe_operation(path, operation)
        preview += f"Safety check: {message}\n"
        
        return preview