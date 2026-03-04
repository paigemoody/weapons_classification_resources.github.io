#!/usr/bin/env python3
"""
Validator for flowchart-structure.txt

Checks for:
  - Valid node IDs (alphanumeric + underscore only, no spaces within ID)
  - Valid node types (decision or classification)
  - Proper tree hierarchy
  - No duplicate node IDs
  - Correct box-drawing character usage
  
Pattern enforced:
  - Root node: NodeId (no metadata required)
  - Other nodes: NodeId or NodeId (metadata) where metadata is:
    - (decision: description)
    - (classification)
"""

import re
import sys
from pathlib import Path


class StructureValidator:
    """Validates weapons classification structure files"""
    
    def __init__(self, filepath):
        self.filepath = filepath
        self.errors = []
        self.warnings = []
        self.nodes = {}
        self.lines = []
    
    def load_file(self):
        """Load the structure file"""
        try:
            with open(self.filepath) as f:
                self.lines = f.readlines()
        except FileNotFoundError:
            self.errors.append(f"File not found: {self.filepath}")
            return False
        return True
    
    def validate_node_id(self, node_id, line_num):
        """Check if node ID is valid (alphanumeric + underscore only, no spaces)"""
        if not re.match(r'^\w+$', node_id):
            self.errors.append(
                f"Line {line_num}: Invalid node ID '{node_id}'. "
                f"Node IDs must contain only letters, numbers, and underscores (no spaces or dashes)."
            )
            return False
        return True
    
    def parse_line(self, line, line_num, is_first_node=False):
        """
        Parse a line and extract node information.
        
        Root node (first node): NodeId (no metadata required)
        Other nodes: NodeId or NodeId (metadata) where metadata is:
          - (decision: description text)
          - (classification)
        
        Returns: (indent_level, node_id, node_type, metadata) or None if invalid
        """
        if not line.strip():
            return None
        
        # Check for valid box-drawing characters
        indent_match = re.match(r'^([\s│├└─]*)', line)
        if not indent_match:
            self.errors.append(f"Line {line_num}: Invalid characters at start of line")
            return None
        
        indent_str = indent_match.group(1)
        indent_level = len(indent_str) // 4
        
        # Remove ONLY box-drawing characters, preserve spaces
        cleaned = re.sub(r'[├├─│└└─]', '', line).strip()
        
        if not cleaned:
            return None
        
        # Root node: just NodeId with no metadata
        if is_first_node:
            match = re.match(r'^(\w+)$', cleaned)
            if not match:
                self.errors.append(
                    f"Line {line_num}: Root node must be a single node ID with no metadata. "
                    f"Found: '{cleaned}'"
                )
                return None
            
            node_id = match.group(1)
            
            if not self.validate_node_id(node_id, line_num):
                return None
            
            if indent_level != 0:
                self.errors.append(
                    f"Line {line_num}: Root node must have no indentation"
                )
                return None
            
            return (indent_level, node_id, "root", "")
        
        # Non-root nodes: NodeId or NodeId (metadata)
        # Try pattern with metadata first: NodeId (metadata)
        match_with_metadata = re.match(r'^(\w+) \((.+)\)$', cleaned)
        
        # Try pattern without metadata: just NodeId
        match_without_metadata = re.match(r'^(\w+)$', cleaned)
        
        if match_with_metadata:
            node_id = match_with_metadata.group(1)
            metadata = match_with_metadata.group(2)
        elif match_without_metadata:
            node_id = match_without_metadata.group(1)
            metadata = ""
        else:
            # If it doesn't match either pattern, give detailed error
            # Check if there are spaces in what looks like a node ID
            match_invalid = re.match(r'^(\S+)\s+', cleaned)
            if match_invalid:
                potential_id = match_invalid.group(1)
                self.errors.append(
                    f"Line {line_num}: Invalid node format '{cleaned}'. "
                    f"Node ID '{potential_id}' contains invalid characters or is followed by extra text. "
                    f"Format must be: NodeId or NodeId (metadata)"
                )
            else:
                self.errors.append(
                    f"Line {line_num}: Invalid node format '{cleaned}'. "
                    f"Format must be: NodeId or NodeId (metadata) where metadata is either:\n"
                    f"    - (decision: description)\n"
                    f"    - (classification)"
                )
            return None
        
        # Validate node ID
        if not self.validate_node_id(node_id, line_num):
            return None
        
        # If no metadata, it's a classification node
        if not metadata:
            return (indent_level, node_id, "classification", "")
        
        # Validate metadata format
        if metadata.lower() == "classification":
            node_type = "classification"
        elif metadata.lower().startswith("decision:"):
            node_type = "decision"
            decision_text = metadata[9:].strip()  # Get text after "decision:"
            if not decision_text:
                self.errors.append(
                    f"Line {line_num}: Decision metadata cannot be empty. "
                    f"Format: (decision: description of choice)"
                )
                return None
        else:
            self.errors.append(
                f"Line {line_num}: Invalid metadata '{metadata}'. "
                f"Must be either:\n"
                f"    - (classification)\n"
                f"    - (decision: description)"
            )
            return None
        
        return (indent_level, node_id, node_type, metadata)
    
    def validate_structure(self):
        """Validate the overall tree structure"""
        parsed_lines = []
        is_first_node = True
        found_any_nodes = False
        
        for line_num, line in enumerate(self.lines, 1):
            parsed = self.parse_line(line, line_num, is_first_node=is_first_node)
            if parsed:
                is_first_node = False
                found_any_nodes = True
                indent_level, node_id, node_type, metadata = parsed
                
                # Check for duplicate IDs
                if node_id in self.nodes:
                    self.errors.append(
                        f"Line {line_num}: Duplicate node ID '{node_id}' "
                        f"(previously defined on line {self.nodes[node_id]['line']})"
                    )
                
                self.nodes[node_id] = {
                    "line": line_num,
                    "type": node_type,
                    "indent": indent_level,
                    "metadata": metadata
                }
                
                parsed_lines.append((line_num, indent_level, node_id, node_type))
        
        # Check if file has any valid nodes
        if not found_any_nodes:
            self.errors.append("No valid nodes found in file. File must contain at least a root node.")
            return False
        
        # Check hierarchy consistency
        if parsed_lines:
            # Check indent increases by 1 level max
            for i in range(1, len(parsed_lines)):
                prev_indent = parsed_lines[i-1][1]
                curr_indent = parsed_lines[i][1]
                
                if curr_indent > prev_indent + 1:
                    self.errors.append(
                        f"Line {parsed_lines[i][0]}: Indent jump too large "
                        f"(from level {prev_indent} to {curr_indent})"
                    )
        
        return len(self.errors) == 0
    
    def validate_decision_rules(self):
        """Validate decision node consistency"""
        for node_id, node_info in self.nodes.items():
            if node_info["type"] == "decision":
                # Decision nodes should have explanatory metadata
                decision_text = node_info["metadata"][9:].strip()  # Get text after "decision:"
                if not decision_text:
                    self.warnings.append(
                        f"Line {node_info['line']}: Decision node '{node_id}' "
                        f"has empty description. Consider adding explanation."
                    )
    
    def validate(self):
        """Run all validations"""
        if not self.load_file():
            return False
        
        if not self.validate_structure():
            return False
        
        self.validate_decision_rules()
        
        return len(self.errors) == 0
    
    def print_report(self):
        """Print validation report"""
        if self.errors:
            print(f"❌ {len(self.errors)} error(s) found:")
            for error in self.errors:
                print(f"   {error}")
        
        if self.warnings:
            print(f"⚠️  {len(self.warnings)} warning(s):")
            for warning in self.warnings:
                print(f"   {warning}")
        
        if not self.errors and not self.warnings:
            print("✅ Structure is valid")
            print(f"   Total nodes: {len(self.nodes)}")
            decisions = sum(1 for n in self.nodes.values() if n["type"] == "decision")
            classifications = sum(1 for n in self.nodes.values() if n["type"] == "classification")
            print(f"   Decision nodes: {decisions}")
            print(f"   Classification nodes: {classifications}")


def main():
    """Main validation"""
    validator = StructureValidator("flowchart-structure.txt")
    
    if validator.validate():
        print("\n✅ Validation passed!")
        validator.print_report()
        return 0
    else:
        print("\n❌ Validation failed!")
        validator.print_report()
        return 1


if __name__ == "__main__":
    sys.exit(main())
