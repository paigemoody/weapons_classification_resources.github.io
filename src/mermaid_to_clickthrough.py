#!/usr/bin/env python3
"""
Convert a Mermaid decision flowchart into a click-through HTML classifier.

Key behavior:
- Current node label becomes the QUESTION for that step.
- Child node labels become OPTION labels.
- Option labels are simplified (e.g., "Handguns - Which bore type best fits?" -> "Handguns").
- Leaf nodes become final results.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Dict, List, Set


EDGE_RE = re.compile(r"^\s*([A-Za-z0-9_]+)\s*-->\s*([A-Za-z0-9_]+)\s*$")
NODE_RE = re.compile(r'^\s*([A-Za-z0-9_]+)\s*\[\s*"([\s\S]*?)"\s*\]\s*$')


def clean_mermaid_label(raw: str) -> str:
    """Strip Mermaid/HTML formatting into readable text."""
    text = raw
    text = re.sub(r"<img[^>]*>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<br\s*/?>", " ", text, flags=re.IGNORECASE)
    text = text.replace("**", "")
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def simplify_option_label(label: str) -> str:
    """
    Turn verbose node labels into clean option labels.
    Examples:
      "Handguns - Which bore type best fits?" -> "Handguns"
      "Rifles: Which sub-type matches best?" -> "Rifles"
      "Long Guns - Which bore type best fits?" -> "Long Guns"
    """
    # Remove trailing question fragments after separators
    for sep in [" - ", ": "]:
        if sep in label:
            left, right = label.split(sep, 1)
            if "which" in right.lower() or "?" in right:
                return left.strip()

    # If whole thing is a question, keep as-is (rare for options)
    return label.strip()


def parse_mermaid(text: str):
    labels: Dict[str, str] = {}
    children: Dict[str, List[str]] = {}
    all_nodes: Set[str] = set()

    for line in text.splitlines():
        if not line.strip() or line.strip().startswith("%%") or line.strip().startswith("flowchart"):
            continue

        m_node = NODE_RE.match(line.rstrip())
        if m_node:
            node_id, raw_label = m_node.groups()
            labels[node_id] = clean_mermaid_label(raw_label)
            all_nodes.add(node_id)
            children.setdefault(node_id, [])
            continue

        m_edge = EDGE_RE.match(line.rstrip())
        if m_edge:
            src, dst = m_edge.groups()
            all_nodes.update([src, dst])
            children.setdefault(src, []).append(dst)
            children.setdefault(dst, [])
            continue

    # Fallback label for unnamed nodes
    for nid in all_nodes:
        labels.setdefault(nid, nid.replace("_", " "))

    return labels, children, all_nodes


def build_tree(node_id: str, labels: Dict[str, str], children: Dict[str, List[str]], stack=None):
    """Build nested tree for React UI."""
    if stack is None:
        stack = set()
    if node_id in stack:
        return {"question": labels[node_id], "options": []}  # break cycles safely

    stack = set(stack)
    stack.add(node_id)

    kids = children.get(node_id, [])
    question = labels[node_id]

    node = {"question": question, "options": []}

    for child in kids:
        grandkids = children.get(child, [])
        option_label = simplify_option_label(labels.get(child, child))

        opt = {
            "label": option_label,
            "image": ""
        }

        if grandkids:
            opt["next"] = build_tree(child, labels, children, stack)
        else:
            # Final result uses full child label (not simplified)
            opt["result"] = labels.get(child, child)

        node["options"].append(opt)

    return node


def make_html(tree_obj: dict, title: str) -> str:
    tree_json = json.dumps(tree_obj, indent=2, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
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
        for (const choiceIndex of path) {{
          const option = node?.options?.[choiceIndex];
          if (!option) return null;
          if (option.next) node = option.next;
          else return null;
        }}
        return node;
      }};

      const handleChoice = (index) => {{
        const currentNode = getCurrentNode();
        const choice = currentNode?.options?.[index];
        if (!choice) return;

        if (choice.result) setResult(choice.result);
        else if (choice.next) setPath([...path, index]);
      }};

      const goBack = () => {{
        if (result) setResult(null);
        else if (path.length > 0) setPath(path.slice(0, -1));
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
              <h1 className="text-3xl font-bold text-slate-800 mb-6 text-center">{title}</h1>

              {{path.length > 0 && !result && (
                <div className="mb-6 text-sm text-slate-600">
                  Step {{path.length + 1}}
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
                    className="mt-6 bg-slate-600 text-white px-6 py-3 rounded-lg hover:bg-slate-700 transition-colors"
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
                    {{(path.length > 0 || result) && (
                      <button onClick={{goBack}} className="px-4 py-2 text-slate-600 hover:text-slate-800">
                        ← Back
                      </button>
                    )}}
                    <button onClick={{reset}} className="ml-auto px-4 py-2 text-slate-600 hover:text-slate-800">
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

    const root = ReactDOM.createRoot(document.getElementById("root"));
    root.render(<ClassificationGuide />);
  </script>
</body>
</html>
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--root", default="SmallArms")
    parser.add_argument("--title", default="Classification Guide")
    args = parser.parse_args()

    text = Path(args.input).read_text(encoding="utf-8")
    labels, children, all_nodes = parse_mermaid(text)

    if args.root not in all_nodes:
        raise ValueError(f"Root '{args.root}' not found in diagram.")

    tree = build_tree(args.root, labels, children)
    html = make_html(tree, args.title)
    Path(args.output).write_text(html, encoding="utf-8")

    print(f"✅ Wrote {args.output}")


if __name__ == "__main__":
    main()
