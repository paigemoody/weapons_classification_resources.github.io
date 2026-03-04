import json
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple
from collections import defaultdict


class TaxonomyToMermaid:
    """Converts taxonomy.json to Mermaid flowchart with images."""
    
    def __init__(self, input_json: str, output_mmd: str):
        self.input_json = Path(input_json)
        self.output_mmd = Path(output_mmd)
        self.taxonomy = None
        self.nodes = {}  # id -> label
        self.edges = []  # (source_id, target_id, label)
        self.image_map = {}  # classification_name -> first_image_url
    
    def load_taxonomy(self):
        """Load taxonomy.json"""
        with open(self.input_json) as f:
            self.taxonomy = json.load(f)
        print(f"✅ Loaded {len(self.taxonomy['classifications'])} classifications")
    
    def build_image_map(self):
        """Build map of classification names to image URLs"""
        for classification in self.taxonomy['classifications']:
            name = classification['name']
            images = classification.get('images', [])
            
            if images:
                img = images[0]
                source = img.get('source_name', '')
                filename = img.get('filename', '')
                
                if source and filename:
                    url = f"https://github.com/paigemoody/weapons_classification_resources.github.io/blob/gh-pages/sources/{source}/visuals/{filename}?raw=true"
                    self.image_map[name] = url
    
    def get_node_id(self, text: str) -> str:
        """Convert text to valid Mermaid node ID"""
        node_id = text.replace(' ', '_').replace('-', '_').replace('.', '').replace('(', '').replace(')', '')
        return node_id
    
    def escape_label(self, text: str) -> str:
        """Escape special characters for Mermaid labels"""
        # Don't escape quotes inside HTML - Mermaid uses double quotes for the label wrapper
        return text
    
    def build_hierarchy_from_taxonomy(self):
        """Build Mermaid nodes and edges from taxonomy hierarchy"""
        
        # Track all unique paths through the hierarchy
        paths = defaultdict(list)
        
        for classification in self.taxonomy['classifications']:
            levels = classification['arcs_levels']
            level_1 = levels['level_1']
            level_2 = levels['level_2']
            level_3 = levels['level_3']
            level_4 = levels['level_4']
            
            # Build the path: level_1 -> level_2 -> level_3 -> level_4
            path = (level_1, level_2, level_3, level_4)
            paths[path].append(classification)
        
        # Create nodes for all unique hierarchy levels
        seen_nodes = set()
        
        # Add root node
        root_id = self.get_node_id('Small_Arms')
        self.nodes[root_id] = '<h1>Which Small Arms group best fits?</h1><p></p><img src="" />'
        seen_nodes.add(root_id)
        
        # Add nodes and edges for each path
        for path_tuple, classifications in sorted(paths.items()):
            level_1, level_2, level_3, level_4 = path_tuple
            
            # level_1 -> level_2
            level_2_id = self.get_node_id(level_2)
            if level_2_id not in seen_nodes:
                # Determine label based on level_2
                if level_2 == 'Handgun':
                    label = '<h1>Which barrel type best fits what you see?</h1><p></p><img src="https://github.com/paigemoody/weapons_classification_resources.github.io/blob/gh-pages/sources/small_arms_survey/visuals/Figure_3.4_Rifled_and_smooth-bore_barrels.png?raw=true" />'
                elif level_2 == 'Long Gun':
                    label = '<h1>Which barrel type best fits?</h1><p></p><img src="" />'
                else:
                    label = f'<h1>{level_2}</h1><p></p><img src="" />'
                
                self.nodes[level_2_id] = label
                seen_nodes.add(level_2_id)
                
                # Edge from root to level_2
                if level_2 == 'Handgun':
                    edge_label = '<h1>Handgun</h1><p>a firearm which is grasped by placing both the control hand and support hand around the pistol grip, and which may be readily fired with one hand (ARES p37)</p><img src="https://github.com/paigemoody/weapons_classification_resources.github.io/blob/gh-pages/sources/ARES_arms_munitions_classification_system/visuals/Figure2.8_2.9_2.10_Handguns.png?raw=true" />'
                elif level_2 == 'Long Gun':
                    edge_label = '<h1>Long Gun</h1><p>A firearm which is grasped by placing the control hand and support hand in different locations, and which is typically fitted with a buttstock intended to be braced against the user\'s shoulder when fired.</p><img src="" />'
                else:
                    edge_label = f'<h1>{level_2}</h1><p></p><img src="" />'
                
                self.edges.append((root_id, level_2_id, edge_label))
            
            # level_2 -> level_3
            level_3_id = self.get_node_id(level_3)
            if level_3_id not in seen_nodes:
                # Determine label for level_3 node
                if level_2 in ['Handgun', 'Long Gun'] and level_3 in ['Rifled', 'Smooth Bore']:
                    if level_2 == 'Handgun':
                        node_label = '<h1>Which type of rifled handgun best matches?</h1><p></p><img src="" />'
                    else:  # Long Gun
                        node_label = '<h1>Which type of rifled long gun best matches?</h1><p></p><img src="" />'
                elif level_3 == 'Rifle':
                    node_label = '<h1>Rifles: Which sub-type of rifled long guns matches best?</h1><p></p><img src="" />'
                elif level_3 == 'Shotgun':
                    node_label = '<h1>How is ammunition loaded into the shotgun?</h1><p></p><img src="" />'
                else:
                    node_label = f'<h1>{level_3}</h1><p></p><img src="" />'
                
                self.nodes[level_3_id] = node_label
                seen_nodes.add(level_3_id)
                
                # Edge label from level_2 to level_3
                edge_label = f'<h1>{level_3}</h1><p></p><img src="" />'
                self.edges.append((level_2_id, level_3_id, edge_label))
            
            # level_3 -> level_4 (leaf nodes)
            level_4_id = self.get_node_id(level_4)
            if level_4_id not in seen_nodes:
                img_url = self.image_map.get(level_4, '')
                node_label = f'<h1>{level_4}</h1><p></p><img src="{img_url}" />'
                self.nodes[level_4_id] = node_label
                seen_nodes.add(level_4_id)
            
            # Edge label from level_3 to level_4
            edge_label = f'<h1>{level_4}</h1><p></p><img src="" />'
            self.edges.append((level_3_id, level_4_id, edge_label))
    
    def generate_mermaid(self) -> str:
        """Generate Mermaid flowchart syntax"""
        lines = ['flowchart TB']
        
        # Add all nodes with proper quote escaping
        for node_id, label in self.nodes.items():
            # Use single quotes inside to avoid escaping hell with Mermaid
            lines.append(f"  {node_id}[\"{label}\"]")
        
        lines.append('')
        
        # Add all edges with proper quote escaping
        for source_id, target_id, edge_label in self.edges:
            lines.append(f"  {source_id} --> |\"{edge_label}\"| {target_id}")
        
        return '\n'.join(lines)
    
    def write_mermaid(self, content: str):
        """Write Mermaid content to file"""
        with open(self.output_mmd, 'w') as f:
            f.write(content)
        print(f"✅ Generated {self.output_mmd}")
        print(f"   Nodes: {len(self.nodes)}")
        print(f"   Edges: {len(self.edges)}")
    
    def run(self):
        """Execute the conversion"""
        self.load_taxonomy()
        self.build_image_map()
        self.build_hierarchy_from_taxonomy()
        mermaid_content = self.generate_mermaid()
        self.write_mermaid(mermaid_content)


def main():
    """Command-line interface"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Convert taxonomy.json to Mermaid flowchart')
    parser.add_argument('--input-json', default='taxonomy.json', help='Input taxonomy.json file')
    parser.add_argument('--output-mmd', default='weapons-classification-flowchart.mmd', help='Output Mermaid file')
    
    args = parser.parse_args()
    
    try:
        converter = TaxonomyToMermaid(args.input_json, args.output_mmd)
        converter.run()
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()