#!/usr/bin/env python3
"""
Unit tests for validate_structure.py
Tests the validator against various valid and invalid structures.
"""

import unittest
import tempfile
import os
from src.validate_structure import StructureValidator


class TestValidateStructure(unittest.TestCase):
    """Test cases for structure validator"""
    
    def create_temp_structure(self, content):
        """Helper to create temporary structure file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(content)
            return f.name
    
    def tearDown(self):
        """Clean up temp files"""
        if hasattr(self, 'temp_file') and os.path.exists(self.temp_file):
            os.unlink(self.temp_file)
    
    # ===== VALID STRUCTURES =====
    
    def test_valid_root_node(self):
        """Root node with no metadata should be valid"""
        content = "SmallArms\n"
        self.temp_file = self.create_temp_structure(content)
        validator = StructureValidator(self.temp_file)
        self.assertTrue(validator.validate())
        self.assertEqual(len(validator.errors), 0)
    
    def test_valid_simple_tree(self):
        """Simple valid tree structure"""
        content = """SmallArms
├── Handguns (decision: Rifled vs Smooth Bore)
│   ├── Rifled_Pistols (classification)
│   └── Revolvers (classification)
└── LongGuns (classification)
"""
        self.temp_file = self.create_temp_structure(content)
        validator = StructureValidator(self.temp_file)
        self.assertTrue(validator.validate())
        self.assertEqual(len(validator.errors), 0)
    
    def test_valid_complex_tree(self):
        """Complex valid tree with multiple levels"""
        content = """SmallArms
├── Handguns (decision: Rifled vs Smooth Bore)
│   ├── Handguns_Rifled (decision: Self-Loading vs Revolver)
│   │   ├── Pistols (classification)
│   │   └── Revolvers (classification)
│   └── SmoothBore_Handguns (classification)
└── LongGuns (decision: Rifled vs Smooth Bore)
    ├── Rifles (classification)
    └── Shotguns (decision: Auto vs Semi)
        ├── AutoShotguns (classification)
        └── SemiShotguns (classification)
"""
        self.temp_file = self.create_temp_structure(content)
        validator = StructureValidator(self.temp_file)
        self.assertTrue(validator.validate())
        self.assertEqual(len(validator.errors), 0)
    
    def test_valid_classification_node_with_metadata(self):
        """Classification node with explicit (classification) metadata"""
        content = """SmallArms
└── Handguns (classification)
    └── Pistols (classification)
"""
        self.temp_file = self.create_temp_structure(content)
        validator = StructureValidator(self.temp_file)
        self.assertTrue(validator.validate())
        self.assertEqual(len(validator.errors), 0)
    
    def test_valid_classification_node_without_metadata(self):
        """Classification node without any metadata"""
        content = """SmallArms
└── Handguns
    └── Pistols
"""
        self.temp_file = self.create_temp_structure(content)
        validator = StructureValidator(self.temp_file)
        self.assertTrue(validator.validate())
        self.assertEqual(len(validator.errors), 0)
    
    def test_valid_decision_with_description(self):
        """Decision node with detailed description"""
        content = """SmallArms
└── Weapons (decision: This is a detailed description of the choice)
    ├── Option1 (classification)
    └── Option2 (classification)
"""
        self.temp_file = self.create_temp_structure(content)
        validator = StructureValidator(self.temp_file)
        self.assertTrue(validator.validate())
        self.assertEqual(len(validator.errors), 0)
    
    def test_valid_mixed_with_and_without_metadata(self):
        """Mix of nodes with and without metadata"""
        content = """SmallArms
├── Category1 (decision: Type A vs Type B)
│   ├── SubCategory1
│   └── SubCategory2 (classification)
└── Category2
    ├── Item1 (classification)
    └── Item2
"""
        self.temp_file = self.create_temp_structure(content)
        validator = StructureValidator(self.temp_file)
        self.assertTrue(validator.validate())
        self.assertEqual(len(validator.errors), 0)
    
    # ===== INVALID NODE IDS =====
    
    def test_invalid_node_id_with_space(self):
        """Node ID with space should fail"""
        content = """SmallArms
└── Semi Automatic (classification)
"""
        self.temp_file = self.create_temp_structure(content)
        validator = StructureValidator(self.temp_file)
        self.assertFalse(validator.validate())
        self.assertTrue(any("Invalid node format" in e or "Invalid node ID" in e for e in validator.errors))
    
    def test_invalid_node_id_with_dash(self):
        """Node ID with dash should fail"""
        content = """SmallArms
└── Semi-Automatic (classification)
"""
        self.temp_file = self.create_temp_structure(content)
        validator = StructureValidator(self.temp_file)
        self.assertFalse(validator.validate())
        self.assertTrue(any("Invalid node ID" in e for e in validator.errors))
    
    def test_invalid_extra_text_before_parens(self):
        """Extra text between node ID and parentheses"""
        content = """SmallArms
└── SemiAutomaticRifles LOLOL (classification)
"""
        self.temp_file = self.create_temp_structure(content)
        validator = StructureValidator(self.temp_file)
        self.assertFalse(validator.validate())
        self.assertTrue(any("Invalid node format" in e for e in validator.errors))
    
    def test_invalid_no_space_before_parens(self):
        """No space between node ID and parentheses"""
        content = """SmallArms
└── SemiAutomaticRifles(classification)
"""
        self.temp_file = self.create_temp_structure(content)
        validator = StructureValidator(self.temp_file)
        self.assertFalse(validator.validate())
        self.assertTrue(any("Invalid node format" in e for e in validator.errors))
    
    def test_invalid_double_space_before_parens(self):
        """Multiple spaces between node ID and parentheses"""
        content = """SmallArms
└── SemiAutomaticRifles  (classification)
"""
        self.temp_file = self.create_temp_structure(content)
        validator = StructureValidator(self.temp_file)
        self.assertFalse(validator.validate())
        self.assertTrue(any("Invalid node format" in e for e in validator.errors))
    
    # ===== INVALID METADATA =====
    
    def test_invalid_metadata_type(self):
        """Invalid metadata type"""
        content = """SmallArms
└── Weapons (invalid_type)
"""
        self.temp_file = self.create_temp_structure(content)
        validator = StructureValidator(self.temp_file)
        self.assertFalse(validator.validate())
        self.assertTrue(any("Invalid metadata" in e for e in validator.errors))
    
    def test_invalid_decision_empty_description(self):
        """Decision with empty description"""
        content = """SmallArms
└── Weapons (decision:)
"""
        self.temp_file = self.create_temp_structure(content)
        validator = StructureValidator(self.temp_file)
        self.assertFalse(validator.validate())
        self.assertTrue(any("Decision metadata cannot be empty" in e for e in validator.errors))
    
    def test_invalid_decision_no_colon(self):
        """Decision without colon"""
        content = """SmallArms
└── Weapons (decision Option A vs Option B)
"""
        self.temp_file = self.create_temp_structure(content)
        validator = StructureValidator(self.temp_file)
        self.assertFalse(validator.validate())
        self.assertTrue(any("Invalid metadata" in e for e in validator.errors))
    
    # ===== DUPLICATE IDS =====
    
    def test_duplicate_node_ids(self):
        """Duplicate node IDs should fail"""
        content = """SmallArms
├── Weapons (decision: Type A vs Type B)
│   ├── Rifle (classification)
│   └── Rifle (classification)
└── Other (classification)
"""
        self.temp_file = self.create_temp_structure(content)
        validator = StructureValidator(self.temp_file)
        self.assertFalse(validator.validate())
        self.assertTrue(any("Duplicate node ID" in e for e in validator.errors))
    
    def test_duplicate_across_branches(self):
        """Duplicate node IDs across different branches"""
        content = """SmallArms
├── Handguns
│   └── Pistol (classification)
└── LongGuns
    └── Pistol (classification)
"""
        self.temp_file = self.create_temp_structure(content)
        validator = StructureValidator(self.temp_file)
        self.assertFalse(validator.validate())
        self.assertTrue(any("Duplicate node ID" in e for e in validator.errors))
    
    # ===== INDENTATION ISSUES =====
    
    def test_invalid_indent_jump(self):
        """Indentation jump > 1 level"""
        content = """SmallArms
├── Weapons (decision: A vs B)
│       ├── Too_Deep (classification)
│       └── Other (classification)
"""
        self.temp_file = self.create_temp_structure(content)
        validator = StructureValidator(self.temp_file)
        self.assertFalse(validator.validate())
        self.assertTrue(any("Indent jump too large" in e for e in validator.errors))
    
    def test_valid_proper_indent_levels(self):
        """Proper indent progression"""
        content = """SmallArms
├── Level1 (decision: A vs B)
│   ├── Level2a (decision: C vs D)
│   │   ├── Level3a (classification)
│   │   └── Level3b (classification)
│   └── Level2b (classification)
└── Other (classification)
"""
        self.temp_file = self.create_temp_structure(content)
        validator = StructureValidator(self.temp_file)
        self.assertTrue(validator.validate())
        self.assertEqual(len(validator.errors), 0)
    
    # ===== ROOT NODE RULES =====
    
    def test_root_with_metadata_fails(self):
        """Root node should not have metadata"""
        content = """SmallArms (classification)
└── Weapons (decision: A vs B)
"""
        self.temp_file = self.create_temp_structure(content)
        validator = StructureValidator(self.temp_file)
        self.assertFalse(validator.validate())
        self.assertTrue(any("Root node must be a single node ID" in e for e in validator.errors))
    
    def test_root_with_indentation_fails(self):
        """Root node must have no indentation"""
        content = """  SmallArms
└── Weapons (classification)
"""
        self.temp_file = self.create_temp_structure(content)
        validator = StructureValidator(self.temp_file)
        self.assertFalse(validator.validate())
        self.assertTrue(any("Root node must have no indentation" in e for e in validator.errors))
    
    # ===== NODE COUNTING =====
    
    def test_node_counting(self):
        """Validator should count nodes correctly"""
        content = """SmallArms
├── Handguns (decision: Rifled vs Smooth)
│   ├── Rifles (classification)
│   └── Pistols (classification)
└── LongGuns (classification)
"""
        self.temp_file = self.create_temp_structure(content)
        validator = StructureValidator(self.temp_file)
        validator.validate()
        
        self.assertEqual(len(validator.nodes), 5)
        decisions = sum(1 for n in validator.nodes.values() if n["type"] == "decision")
        classifications = sum(1 for n in validator.nodes.values() if n["type"] == "classification")
        
        self.assertEqual(decisions, 1)
        self.assertEqual(classifications, 3)
    
    # ===== FILE ERRORS =====
    
    def test_nonexistent_file(self):
        """Nonexistent file should error"""
        validator = StructureValidator("/nonexistent/path/file.txt")
        self.assertFalse(validator.validate())
        self.assertTrue(any("File not found" in e for e in validator.errors))


class TestValidateStructureEdgeCases(unittest.TestCase):
    """Edge case tests"""
    
    def create_temp_structure(self, content):
        """Helper to create temporary structure file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(content)
            return f.name
    
    def tearDown(self):
        """Clean up temp files"""
        if hasattr(self, 'temp_file') and os.path.exists(self.temp_file):
            os.unlink(self.temp_file)
    
    def test_empty_file(self):
        """Empty file should fail"""
        content = ""
        self.temp_file = self.create_temp_structure(content)
        validator = StructureValidator(self.temp_file)
        self.assertFalse(validator.validate())
        self.assertTrue(any("No valid nodes found" in e for e in validator.errors))
    
    def test_only_whitespace(self):
        """File with only whitespace should fail"""
        content = "   \n\n   \n"
        self.temp_file = self.create_temp_structure(content)
        validator = StructureValidator(self.temp_file)
        self.assertFalse(validator.validate())
        self.assertTrue(any("No valid nodes found" in e for e in validator.errors))
    
    def test_numeric_node_ids(self):
        """Numeric node IDs should be valid"""
        content = """SmallArms
└── Category123 (classification)
"""
        self.temp_file = self.create_temp_structure(content)
        validator = StructureValidator(self.temp_file)
        self.assertTrue(validator.validate())
    
    def test_underscore_node_ids(self):
        """Node IDs with underscores should be valid"""
        content = """SmallArms
└── My_Category_Name (classification)
"""
        self.temp_file = self.create_temp_structure(content)
        validator = StructureValidator(self.temp_file)
        self.assertTrue(validator.validate())
    
    def test_long_description(self):
        """Decision with very long description"""
        content = """SmallArms
└── Weapons (decision: This is a very long description that explains the choice between many different options and subcategories of weapons classification systems)
    ├── Type1 (classification)
    └── Type2 (classification)
"""
        self.temp_file = self.create_temp_structure(content)
        validator = StructureValidator(self.temp_file)
        self.assertTrue(validator.validate())
    
    def test_special_chars_in_description(self):
        """Description with special characters"""
        content = """SmallArms
└── Weapons (decision: Type A/B vs Type C-D (modern))
    ├── Type1 (classification)
    └── Type2 (classification)
"""
        self.temp_file = self.create_temp_structure(content)
        validator = StructureValidator(self.temp_file)
        self.assertTrue(validator.validate())
    
    def test_deep_nesting(self):
        """Deeply nested valid structure"""
        content = """SmallArms
└── Level1
    └── Level2
        └── Level3
            └── Level4
                └── Level5
                    └── DeepNode (classification)
"""
        self.temp_file = self.create_temp_structure(content)
        validator = StructureValidator(self.temp_file)
        self.assertTrue(validator.validate())
    
    def test_many_siblings(self):
        """Many sibling nodes"""
        content = """SmallArms
├── Node1 (classification)
├── Node2 (classification)
├── Node3 (classification)
├── Node4 (classification)
├── Node5 (classification)
├── Node6 (classification)
├── Node7 (classification)
└── Node8 (classification)
"""
        self.temp_file = self.create_temp_structure(content)
        validator = StructureValidator(self.temp_file)
        self.assertTrue(validator.validate())
        self.assertEqual(len(validator.nodes), 9)  # Including root


class TestValidateStructureRealWorld(unittest.TestCase):
    """Real-world structure tests"""
    
    def create_temp_structure(self, content):
        """Helper to create temporary structure file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(content)
            return f.name
    
    def tearDown(self):
        """Clean up temp files"""
        if hasattr(self, 'temp_file') and os.path.exists(self.temp_file):
            os.unlink(self.temp_file)
    
    def test_real_weapons_structure(self):
        """Real weapons classification structure"""
        content = """SmallArms
├── Handguns_BarrelType (decision: Rifled vs Smooth Bore)
│   ├── Handguns_Rifled (decision: Self-Loading Pistol vs Revolver)
│   │   ├── Rifled_SelfLoadingPistols (classification)
│   │   └── Rifled_Revolvers (classification)
│   └── SmoothBore_OtherHandguns (classification)
└── LongGuns (decision: Rifled vs Smooth Bore)
    ├── LongGuns_Rifled (decision: SMG vs MPMG vs Rifles)
    │   ├── Rifled_SubMachineGuns (classification)
    │   ├── Rifled_ManPortableMachineGuns (classification)
    │   └── Rifles (decision: Self-Loading vs Manually-Loaded)
    │       ├── SelfLoadingRifles (decision: Auto vs Semi)
    │       │   ├── AutomaticRifles (classification)
    │       │   └── SemiAutomaticRifles (classification)
    │       └── ManuallyOperatedRifles (decision: Break/Bolt/Lever/Pump/Other)
    │           ├── BreakActionRifles (classification)
    │           ├── BoltActionRifles (classification)
    │           ├── LeverActionRifles (classification)
    │           ├── PumpActionRifles (classification)
    │           └── OtherManuallyOperatedRifles (classification)
    └── LongGuns_SmoothBore (decision: Shotguns vs OtherSmoothBoreLongGuns)
        ├── Shotguns (decision: Self-Loading vs Manually-Operated)
        │   ├── SelfLoadingShotguns (decision: Auto vs Semi)
        │   │   ├── AutomaticShotguns (classification)
        │   │   └── SemiAutomaticShotguns (classification)
        │   └── ManuallyOperatedShotguns (decision: Break/Bolt/Lever/Pump/Other)
        │       ├── BreakActionShotguns (classification)
        │       ├── BoltActionShotguns (classification)
        │       ├── LeverActionShotguns (classification)
        │       ├── PumpActionShotguns (classification)
        │       └── OtherManuallyOperatedShotguns (classification)
        └── OtherSmoothBoreLongGuns (classification)
"""
        self.temp_file = self.create_temp_structure(content)
        validator = StructureValidator(self.temp_file)
        self.assertTrue(validator.validate())
        self.assertEqual(len(validator.errors), 0)
        self.assertEqual(len(validator.nodes), 28)


if __name__ == '__main__':
    unittest.main()