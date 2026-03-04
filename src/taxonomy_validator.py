import json
import sys
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime


class TaxonomyValidator:
    """Validates and helps manage the classification taxonomy based on ARES/SAS."""
    
    ALLOWED_IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif'}
    
    # Define the strict schema for each section
    CLASSIFICATION_SCHEMA = {
        'id': str,
        'name': str,
        'arcs_levels': dict,
        'attributes': dict,
        'description': str,
        'images': list
    }
    
    ARCS_LEVELS_SCHEMA = {
        'level_1': str,
        'level_2': str,
        'level_3': str,
        'level_4': str
    }
    
    IMAGE_SCHEMA = {
        'source_name': str,
        'filename': str,
        'caption': str,
        'alt_text': str
    }
    
    def __init__(self, taxonomy_file: str):
        self.taxonomy_file = Path(taxonomy_file)
        self.sources_dir = Path("sources")
        self.load_taxonomy()
    
    def load_taxonomy(self):
        """Load the existing taxonomy."""
        if self.taxonomy_file.exists():
            try:
                with open(self.taxonomy_file) as f:
                    self.data = json.load(f)
            except json.JSONDecodeError as e:
                print(f"❌ Invalid JSON in {self.taxonomy_file}: {e}")
                sys.exit(1)
        else:
            self.data = {
                "metadata": {
                    "version": "1.0",
                    "last_updated": "",
                    "description": "Weapons classification taxonomy based on ARES and SAS",
                    "sources": [
                        "ARES Arms & Munitions Classification System",
                        "SAS Weapons Identification Guide"
                    ]
                },
                "classifications": []
            }
    
    def validate_schema(self, obj: Dict, schema: Dict, obj_name: str) -> List[str]:
        """
        Validate an object against a strict schema.
        
        Args:
            obj: The object to validate
            schema: Dictionary of {field_name: expected_type}
            obj_name: Name of object for error messages
        
        Returns:
            List of error messages
        """
        errors = []
        
        # Check for missing required fields
        for field, expected_type in schema.items():
            if field not in obj:
                errors.append(f"Missing required field '{field}' in {obj_name}")
            elif not isinstance(obj[field], expected_type):
                errors.append(
                    f"Field '{field}' in {obj_name} has wrong type. "
                    f"Expected {expected_type.__name__}, got {type(obj[field]).__name__}"
                )
        
        # Check for unknown/extra fields
        for field in obj.keys():
            if field not in schema:
                errors.append(
                    f"Unknown field '{field}' in {obj_name}. "
                    f"Allowed fields: {', '.join(schema.keys())}"
                )
        
        return errors
    
    def add_classification(
        self,
        classification_id: str,
        name: str,
        level_1: str,
        level_2: str,
        level_3: str,
        level_4: str,
        attributes: Dict[str, Any],
        description: str,
        images: List[Dict[str, str]]
    ) -> bool:
        """
        Add a new classification to the taxonomy.
        
        Args:
            classification_id: Unique identifier (e.g., 'handgun_semi_automatic_pistol')
            name: Display name (e.g., 'Semi-Automatic Pistol')
            level_1-4: ARES/SAS hierarchy levels
            attributes: Dictionary of weapon characteristics
            description: Human-readable description
            images: List of dicts with 'source_name', 'filename', 'caption', 'alt_text'
        
        Returns:
            True if successful, False if validation failed
        """
        # Validate ID uniqueness
        if any(c['id'] == classification_id for c in self.data['classifications']):
            print(f"❌ Error: ID '{classification_id}' already exists")
            return False
        
        # Validate images
        for i, image in enumerate(images):
            # Validate image schema
            image_errors = self.validate_schema(image, self.IMAGE_SCHEMA, f"image[{i}]")
            if image_errors:
                for error in image_errors:
                    print(f"❌ Error: {error}")
                return False
            
            # Check file extension
            filename = Path(image['filename'])
            if filename.suffix.lower() not in self.ALLOWED_IMAGE_EXTENSIONS:
                print(f"❌ Error: Image '{image['filename']}' is not PNG format")
                print(f"   Allowed formats: {self.ALLOWED_IMAGE_EXTENSIONS}")
                return False
            
            # Check file exists
            image_path = self.sources_dir / image['source_name'] / 'visuals' / image['filename']
            if not image_path.exists():
                print(f"❌ Error: Image not found at {image_path}")
                print(f"   Expected: sources/{image['source_name']}/visuals/{image['filename']}")
                return False
        
        # Build classification object
        new_classification = {
            "id": classification_id,
            "name": name,
            "arcs_levels": {
                "level_1": level_1,
                "level_2": level_2,
                "level_3": level_3,
                "level_4": level_4
            },
            "attributes": attributes,
            "description": description,
            "images": images
        }
        
        self.data['classifications'].append(new_classification)
        print(f"✅ Added: {name}")
        return True
    
    def validate_all(self) -> List[str]:
        """
        Validate entire taxonomy against schema and data integrity.
        
        Returns:
            List of error messages (empty if valid)
        """
        errors = []
        
        ids_seen = set()
        for idx, classification in enumerate(self.data['classifications']):
            class_name = f"classification[{idx}] (id: '{classification.get('id', 'unknown')}')"
            
            # Validate classification schema
            schema_errors = self.validate_schema(
                classification,
                self.CLASSIFICATION_SCHEMA,
                class_name
            )
            errors.extend(schema_errors)
            
            if schema_errors:
                continue  # Skip further validation if schema is broken
            
            # Check ID uniqueness
            if classification['id'] in ids_seen:
                errors.append(f"Duplicate ID: {classification['id']}")
            ids_seen.add(classification['id'])
            
            # Validate ARCS levels schema
            arcs_errors = self.validate_schema(
                classification['arcs_levels'],
                self.ARCS_LEVELS_SCHEMA,
                f"{class_name} -> arcs_levels"
            )
            errors.extend(arcs_errors)
            
            # Check image paths and formats
            for img_idx, image in enumerate(classification.get('images', [])):
                img_name = f"{class_name} -> images[{img_idx}]"
                
                # Validate image schema
                img_errors = self.validate_schema(image, self.IMAGE_SCHEMA, img_name)
                errors.extend(img_errors)
                
                if img_errors:
                    continue  # Skip file checks if schema is broken
                
                filename = Path(image['filename'])
                
                # Validate extension
                if filename.suffix.lower() not in self.ALLOWED_IMAGE_EXTENSIONS:
                    errors.append(
                        f"Invalid image format in {img_name}: "
                        f"{image['filename']} (must be PNG)"
                    )
                
                # Validate path
                path = self.sources_dir / image['source_name'] / 'visuals' / image['filename']
                if not path.exists():
                    errors.append(
                        f"Missing image in {img_name}: "
                        f"sources/{image['source_name']}/visuals/{image['filename']}"
                    )
        
        return errors
    
    def save(self):
        """Save taxonomy to file."""
        self.data['metadata']['last_updated'] = datetime.now().isoformat()
        
        with open(self.taxonomy_file, 'w') as f:
            json.dump(self.data, f, indent=2)
        print(f"✅ Saved to {self.taxonomy_file}")
    
    def list_all(self):
        """Print all classifications with their attributes."""
        for c in self.data['classifications']:
            print(f"\n📋 {c['name']}")
            print(f"   ID: {c['id']}")
            levels = c['arcs_levels']
            print(f"   ARES/SAS: {levels['level_1']} > {levels['level_2']} > "
                  f"{levels['level_3']} > {levels['level_4']}")
            print(f"   Images: {len(c.get('images', []))} PNG(s) attached")
            for img in c.get('images', []):
                print(f"      - {img['filename']} ({img['source_name']})")


def main():
    """Command-line interface for taxonomy validation."""
    if len(sys.argv) < 2:
        print("Usage: python3 taxonomy_validator.py <command> [taxonomy_file]")
        print("\nCommands:")
        print("  validate <file>  - Validate taxonomy file against schema")
        print("  list <file>      - List all classifications")
        sys.exit(1)
    
    command = sys.argv[1]
    taxonomy_file = sys.argv[2] if len(sys.argv) > 2 else "taxonomy.json"
    
    validator = TaxonomyValidator(taxonomy_file)
    
    if command == "validate":
        errors = validator.validate_all()
        if errors:
            print("❌ Validation failed:\n")
            for error in errors:
                print(f"   - {error}")
            sys.exit(1)
        else:
            print(f"✅ Taxonomy is valid")
            print(f"   {len(validator.data['classifications'])} classifications")
            print(f"   All schemas compliant")
            print(f"   All image files found")
            sys.exit(0)
    
    elif command == "list":
        print(f"Taxonomy: {taxonomy_file}")
        print(f"Total classifications: {len(validator.data['classifications'])}\n")
        validator.list_all()
        sys.exit(0)
    
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()