import re
import json

def parse_mermaid_flowchart(mermaid_text):
    """
    Convert a Mermaid flowchart to a nested tree structure for the classification guide.
    """
    
    lines = mermaid_text.strip().split('\n')
    nodes = {}
    edges = []
    root_node = None
    
    # Parse node definitions and edges
    for line in lines:
        line = line.strip()
        
        # Skip empty lines, comments, and flowchart declaration
        if not line or line.startswith('%') or line.startswith('flowchart'):
            continue
        
        # Parse node definition: NodeId["Label<br/>image"]
        node_match = re.match(r'(\w+)\["([^"]+)"\]', line)
        if node_match:
            node_id = node_match.group(1)
            label_text = node_match.group(2)
            
            # Extract the main label (everything before <br/> or image tag)
            label = re.split(r'<br/>', label_text)[0].strip()
            
            # Clean up markdown bold
            label = re.sub(r'\*\*([^*]+)\*\*', r'\1', label)
            
            # Extract question if present
            question_match = re.search(r'(Which .+\?|.+\?)', label)
            question = question_match.group(1) if question_match else None
            
            # Remove question from label to get clean category name
            if question:
                label = re.sub(r'Which .+\? ', '', label)
                label = re.sub(r' - .+', '', label)
            
            # Extract image URL if present
            img_match = re.search(r"<img src='([^']*)'", label_text)
            image_url = img_match.group(1) if img_match else ""
            
            nodes[node_id] = {
                'id': node_id,
                'label': label.strip(),
                'question': question,
                'image': image_url,
                'children': []
            }
            
            # First node is root
            if root_node is None:
                root_node = node_id
        
        # Parse edges: NodeA --> NodeB
        edge_match = re.match(r'(\w+)\s*-->\s*(\w+)', line)
        if edge_match:
            from_node = edge_match.group(1)
            to_node = edge_match.group(2)
            edges.append((from_node, to_node))
    
    # Build tree structure from edges
    for from_node, to_node in edges:
        if from_node in nodes and to_node in nodes:
            nodes[from_node]['children'].append(to_node)
    
    # Convert to nested structure
    def build_tree(node_id):
        node = nodes[node_id]
        
        # If no children, this is a leaf (result)
        if not node['children']:
            return {
                'label': node['label'],
                'image': node['image'],
                'result': node['label']
            }
        
        # Build options from children
        options = []
        for child_id in node['children']:
            child_tree = build_tree(child_id)
            options.append(child_tree)
        
        result = {
            'label': node['label'],
            'image': node['image']
        }
        
        # Determine if this node has a question or should inherit from parent
        if node['question']:
            result['question'] = node['question']
            result['options'] = options
            return {'next': result}
        else:
            # This is an intermediate grouping node
            if len(options) == 1 and 'next' in options[0]:
                # Pass through single child's next
                result['next'] = options[0]['next']
            else:
                # Multiple children means we need a question
                result['next'] = {
                    'question': f"Which {node['label'].lower()} type?",
                    'options': options
                }
            return result
    
    # Build from root
    if root_node:
        tree = build_tree(root_node)
        if 'next' in tree:
            return tree['next']
        else:
            # Root is a question node
            return {
                'question': nodes[root_node]['question'] or "Which option best fits?",
                'options': [build_tree(child) for child in nodes[root_node]['children']]
            }
    
    return None


def generate_html(tree, title="Classification Guide"):
    """Generate a complete HTML file with the classification guide"""
    
    tree_json = json.dumps(tree, indent=2)
    
    html_template = f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <script crossorigin src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
  <script crossorigin src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
  <script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body>
  <div id="root"></div>
  
  <script type="text/babel">
    const {{ useState }} = React;

    const ClassificationGuide = () => {{
      const [path, setPath] = useState([]);
      const [result, setResult] = useState(null);

      const tree = {tree_json};

      const getCurrentNode = () => {{
        let node = tree;
        for (const choice of path) {{
          node = node.options[choice].next;
        }}
        return node;
      }};

      const handleChoice = (index) => {{
        const currentNode = getCurrentNode();
        const choice = currentNode.options[index];
        
        if (choice.result) {{
          setResult(choice.result);
        }} else {{
          setPath([...path, index]);
        }}
      }};

      const goBack = () => {{
        if (result) {{
          setResult(null);
        }} else if (path.length > 0) {{
          setPath(path.slice(0, -1));
        }}
      }};

      const reset = () => {{
        setPath([]);
        setResult(null);
      }};

      const currentNode = result ? null : getCurrentNode();

      return (
        <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 p-6">
          <div className="max-w-2xl mx-auto">
            <div className="bg-white rounded-lg shadow-lg p-8">
              <h1 className="text-3xl font-bold text-slate-800 mb-6 text-center">
                {title}
              </h1>

              {{path.length > 0 && !result && (
                <div className="mb-6 text-sm text-slate-600">
                  Step {{path.length + 1}} of classification
                </div>
              )}}

              {{result && (
                <div className="text-center">
                  <div className="mb-6">
                    <div className="w-32 h-32 mx-auto bg-slate-200 rounded-lg flex items-center justify-center mb-4">
                      <span className="text-slate-400 text-sm">Image placeholder</span>
                    </div>
                    <h2 className="text-2xl font-bold text-slate-800 mb-2">Classification Complete</h2>
                    <div className="inline-block bg-blue-100 text-blue-800 px-6 py-3 rounded-lg text-xl font-semibold">
                      {{result}}
                    </div>
                  </div>
                  <button
                    onClick={{reset}}
                    className="mt-6 bg-slate-600 text-white px-6 py-3 rounded-lg hover:bg-slate-700 transition-colors inline-flex items-center gap-2"
                  >
                    ↻ Start Over
                  </button>
                </div>
              )}}

              {{!result && currentNode && (
                <div>
                  <h2 className="text-xl font-semibold text-slate-700 mb-6 text-center">
                    {{currentNode.question}}
                  </h2>

                  <div className="space-y-3">
                    {{currentNode.options.map((option, index) => (
                      <button
                        key={{index}}
                        onClick={{() => handleChoice(index)}}
                        className="w-full bg-white border-2 border-slate-300 rounded-lg p-4 hover:border-blue-500 hover:bg-blue-50 transition-all text-left group"
                      >
                        <div className="flex items-center gap-4">
                          <div className="w-16 h-16 bg-slate-100 rounded flex-shrink-0 flex items-center justify-center overflow-hidden">
                            {{option.image ? (
                              <img src={{option.image}} alt={{option.label}} className="w-full h-full object-cover" />
                            ) : (
                              <span className="text-slate-400 text-xs">Image</span>
                            )}}
                          </div>
                          <div className="text-lg font-medium text-slate-800 group-hover:text-blue-700">
                            {{option.label}}
                          </div>
                        </div>
                      </button>
                    ))}}
                  </div>

                  <div className="mt-8 flex gap-3">
                    {{path.length > 0 && (
                      <button
                        onClick={{goBack}}
                        className="flex items-center gap-2 px-4 py-2 text-slate-600 hover:text-slate-800 transition-colors"
                      >
                        ← Back
                      </button>
                    )}}
                    <button
                      onClick={{reset}}
                      className="ml-auto px-4 py-2 text-slate-600 hover:text-slate-800 transition-colors"
                    >
                      Start Over
                    </button>
                  </div>
                </div>
              )}}
            </div>
          </div>
        </div>
      );
    }};

    const root = ReactDOM.createRoot(document.getElementById('root'));
    root.render(<ClassificationGuide />);
  </script>
</body>
</html>'''
    
    return html_template


if __name__ == "__main__":
    import sys
    
    # Read from stdin or file
    if len(sys.argv) > 1:
        with open(sys.argv[1], 'r') as f:
            mermaid_text = f.read()
    else:
        mermaid_text = sys.stdin.read()
    
    # Parse and convert
    tree = parse_mermaid_flowchart(mermaid_text)
    
    if tree:
        # Generate HTML output
        html = generate_html(tree)
        print(html)
    else:
        print("Error: Could not parse mermaid diagram", file=sys.stderr)
        sys.exit(1)