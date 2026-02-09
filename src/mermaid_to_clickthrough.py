#!/usr/bin/env python3
"""
Convert Mermaid flowchart (.mmd/.mermaid) to interactive click-through HTML.

Enhancements:
- Robust multiline parsing for node and edge labels
- Edge label supports rich HTML (title + context)
- Option image comes from destination node's <img src='...'>
- Preserves HTML in node questions and result screens
- Auto root detection; synthetic start if multiple top nodes
- Cycle detection with explicit abort
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# ---------- Parsing regex ----------
# Node: NodeId["..."]
NODE_BLOCK_RE = re.compile(
    r'([A-Za-z0-9_]+)\s*\[\s*"((?:[^"\\]|\\.|"(?=\s*\]))*?)"\s*\]',
    re.DOTALL
)

# Edge with optional rich label:
# A --> B
# A --> |Label| B
# A --> |"Label with <h1> and <p>"| B
EDGE_BLOCK_RE = re.compile(
    r'([A-Za-z0-9_]+)\s*-->\s*(?:\|\s*(?:"((?:[^"\\]|\\.)*)"|([^|]*?))\s*\|\s*)?([A-Za-z0-9_]+)',
    re.DOTALL
)

IMG_TAG_RE = re.compile(r"<img\b[^>]*>", re.IGNORECASE | re.DOTALL)
SRC_RE = re.compile(r"""src\s*=\s*(['"])(.*?)\1""", re.IGNORECASE | re.DOTALL)
H1_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.IGNORECASE | re.DOTALL)
P_RE = re.compile(r"<p[^>]*>(.*?)</p>", re.IGNORECASE | re.DOTALL)


@dataclass
class EdgeData:
    src: str
    dst: str
    raw_label_html: str  # raw edge label HTML (if any)


class Graph:
    def __init__(self) -> None:
        self.node_html: Dict[str, str] = {}
        self.children: Dict[str, List[str]] = {}
        self.indegree: Dict[str, int] = {}
        self.edge_html: Dict[Tuple[str, str], str] = {}
        self.nodes_in_order: List[str] = []

    def ensure_node(self, nid: str) -> None:
        if nid not in self.node_html:
            self.node_html[nid] = nid.replace("_", " ")
        if nid not in self.children:
            self.children[nid] = []
        if nid not in self.indegree:
            self.indegree[nid] = 0
        if nid not in self.nodes_in_order:
            self.nodes_in_order.append(nid)

    def add_node(self, nid: str, raw_html: str) -> None:
        self.ensure_node(nid)
        self.node_html[nid] = normalize_mermaid_label_html(raw_html)

    def add_edge(self, src: str, dst: str, edge_html: str) -> None:
        self.ensure_node(src)
        self.ensure_node(dst)
        self.children[src].append(dst)
        self.indegree[dst] += 1
        self.edge_html[(src, dst)] = edge_html.strip() if edge_html else ""


def normalize_mermaid_label_html(raw: str) -> str:
    """Keep HTML and transform **bold** -> <strong>bold</strong>."""
    txt = (raw or "").strip()
    txt = txt.replace('\\"', '"')
    txt = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", txt, flags=re.DOTALL)
    return txt


def strip_html(text: str) -> str:
    t = re.sub(r"<br\s*/?>", " ", text or "", flags=re.IGNORECASE)
    t = re.sub(r"<[^>]+>", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def extract_first_img_tag(html: str) -> str:
    m = IMG_TAG_RE.search(html or "")
    return m.group(0).strip() if m else ""


def extract_img_src(img_tag: str) -> str:
    if not img_tag:
        return ""
    m = SRC_RE.search(img_tag)
    if not m:
        return ""
    return m.group(2).strip()


def parse_edge_label(edge_html: str, fallback_text: str) -> Dict[str, str]:
    """
    Parse edge label into:
      - titleHtml
      - contextHtml
      - plainLabel
    Rules:
      - If <h1> exists, title = first h1 innerHTML
      - If <p> exists, context = concatenated paragraphs
      - Else title = entire edge_html
      - plainLabel used for breadcrumbs/accessibility
    """
    html = normalize_mermaid_label_html(edge_html or "")

    if not html:
        plain = strip_html(fallback_text) or fallback_text
        return {
            "titleHtml": plain,
            "contextHtml": "",
            "plainLabel": plain,
        }

    h1_match = H1_RE.search(html)
    p_matches = P_RE.findall(html)

    if h1_match:
        title_html = h1_match.group(1).strip()
    else:
        title_html = html.strip()

    context_html = ""
    if p_matches:
        context_html = "".join(f"<p>{p.strip()}</p>" for p in p_matches)

    plain = strip_html(title_html) or strip_html(html) or fallback_text

    return {
        "titleHtml": title_html,
        "contextHtml": context_html,
        "plainLabel": plain,
    }


def parse_mermaid(text: str) -> Graph:
    g = Graph()

    # Remove comment-only lines and flowchart declaration lines for cleaner parsing
    cleaned_lines = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("%%"):
            continue
        if s.startswith("flowchart"):
            continue
        cleaned_lines.append(line)
    content = "\n".join(cleaned_lines)

    # Parse nodes first
    for m in NODE_BLOCK_RE.finditer(content):
        nid, raw_html = m.group(1), m.group(2)
        g.add_node(nid, raw_html)

    # Parse edges
    for m in EDGE_BLOCK_RE.finditer(content):
        src = m.group(1)
        quoted_lbl = m.group(2)  # from |"..."|
        unquoted_lbl = m.group(3)  # from |...|
        dst = m.group(4)
        raw_edge_label = quoted_lbl if quoted_lbl is not None else (unquoted_lbl or "")
        g.add_edge(src, dst, normalize_mermaid_label_html(raw_edge_label))

    return g


def detect_cycle(g: Graph) -> Optional[List[str]]:
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {n: WHITE for n in g.children}
    parent: Dict[str, Optional[str]] = {n: None for n in g.children}

    def dfs(u: str) -> Optional[List[str]]:
        color[u] = GRAY
        for v in g.children.get(u, []):
            if color[v] == WHITE:
                parent[v] = u
                found = dfs(v)
                if found:
                    return found
            elif color[v] == GRAY:
                cycle = [v]
                cur = u
                while cur is not None and cur != v:
                    cycle.append(cur)
                    cur = parent[cur]
                cycle.append(v)
                cycle.reverse()
                return cycle
        color[u] = BLACK
        return None

    for n in g.nodes_in_order:
        if color[n] == WHITE:
            found = dfs(n)
            if found:
                return found
    return None


def top_nodes(g: Graph) -> List[str]:
    return [n for n in g.nodes_in_order if g.indegree.get(n, 0) == 0]


def build_node(g: Graph, node_id: str) -> dict:
    question_html = g.node_html.get(node_id, node_id.replace("_", " "))
    kids = g.children.get(node_id, [])

    node_obj = {
        "nodeId": node_id,
        "questionHtml": question_html,
        "questionText": strip_html(question_html),
        "options": [],
    }

    for child in kids:
        child_html = g.node_html.get(child, child.replace("_", " "))
        child_kids = g.children.get(child, [])

        # Option label/context from edge
        edge_html = g.edge_html.get((node_id, child), "")
        fallback = strip_html(child_html)
        edge_parts = parse_edge_label(edge_html, fallback)

        # Option image from destination node
        img_tag = extract_first_img_tag(child_html)
        img_src = extract_img_src(img_tag)

        opt = {
            "label": edge_parts["plainLabel"],            # simple text for breadcrumb/button fallback
            "titleHtml": edge_parts["titleHtml"],         # rich title
            "contextHtml": edge_parts["contextHtml"],     # optional supporting paragraph(s)
            "nextNodeId": child,
            "imageTag": img_tag,
            "imageSrc": img_src,
        }

        if child_kids:
            opt["next"] = build_node(g, child)
        else:
            opt["resultHtml"] = child_html
            opt["resultText"] = strip_html(child_html)

        node_obj["options"].append(opt)

    return node_obj


def build_tree(g: Graph) -> dict:
    roots = top_nodes(g)
    if not roots:
        raise ValueError("No top-level node found (in-degree = 0).")

    if len(roots) == 1:
        return build_node(g, roots[0])

    # Synthetic root if multiple tops
    synthetic = {
        "nodeId": "__synthetic_start__",
        "questionHtml": "Where do you want to start?",
        "questionText": "Where do you want to start?",
        "options": [],
    }

    for r in roots:
        r_html = g.node_html.get(r, r.replace("_", " "))
        img_tag = extract_first_img_tag(r_html)
        img_src = extract_img_src(img_tag)
        plain = strip_html(r_html) or r.replace("_", " ")

        synthetic["options"].append({
            "label": plain,
            "titleHtml": plain,
            "contextHtml": "",
            "nextNodeId": r,
            "imageTag": img_tag,
            "imageSrc": img_src,
            "next": build_node(g, r),
        })

    return synthetic


def make_html(tree: dict, app_name: str) -> str:
    tree_json = json.dumps(tree, ensure_ascii=False, indent=2)

    template = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>__APP_NAME_ESC__</title>
  <script crossorigin src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
  <script crossorigin src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
  <script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body>
  <div id="root"></div>

  <script type="text/babel">
    const { useMemo, useState } = React;
    const APP_NAME = __APP_NAME_JSON__;
    const TREE = __TREE_JSON__;

    function ClassificationGuide() {
      const [path, setPath] = useState([]);
      const [result, setResult] = useState(null);

      const getCurrentNode = () => {
        let node = TREE;
        for (const step of path) {
          const opt = node?.options?.[step.optionIndex];
          if (!opt) return node;
          if (opt.next) node = opt.next;
          else return node;
        }
        return node;
      };

      const currentNode = result ? null : getCurrentNode();

      const choose = (idx) => {
        const node = getCurrentNode();
        if (!node) return;
        const opt = node.options?.[idx];
        if (!opt) return;

        const nextPath = [
          ...path,
          {
            optionIndex: idx,
            optionLabel: opt.label || "Option"
          }
        ];

        if (opt.resultHtml || opt.resultText) {
          setPath(nextPath);
          setResult({
            html: opt.resultHtml || opt.resultText || "",
            text: opt.resultText || ""
          });
        } else if (opt.next) {
          setPath(nextPath);
        }
      };

      const goToStep = (stepIndex) => {
        if (stepIndex < 0) {
          setPath([]);
          setResult(null);
          return;
        }
        setPath(path.slice(0, stepIndex + 1));
        setResult(null);
      };

      const backOne = () => {
        if (result) {
          setResult(null);
          return;
        }
        if (path.length > 0) setPath(path.slice(0, -1));
      };

      const reset = () => {
        setPath([]);
        setResult(null);
      };

      const breadcrumbItems = useMemo(() => {
        return path.map((p, i) => ({ label: p.optionLabel, stepIndex: i }));
      }, [path]);

      return (
        <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 p-6">
          <div className="max-w-4xl mx-auto">
            <div className="bg-white rounded-lg shadow-lg p-8">
              <h1 className="text-3xl font-bold text-slate-800 mb-4 text-center">{APP_NAME}</h1>

              <div className="mb-6">
                <div className="text-xs uppercase tracking-wide text-slate-500 mb-2">Path</div>
                <div className="flex flex-wrap items-center gap-2 text-sm">
                  <button
                    onClick={() => goToStep(-1)}
                    className="px-2 py-1 rounded bg-slate-100 hover:bg-slate-200 text-slate-700"
                  >
                    Start
                  </button>
                  {breadcrumbItems.map((b, i) => (
                    <React.Fragment key={i}>
                      <span className="text-slate-400">→</span>
                      <button
                        onClick={() => goToStep(i)}
                        className="px-2 py-1 rounded bg-blue-50 hover:bg-blue-100 text-blue-800"
                      >
                        {b.label}
                      </button>
                    </React.Fragment>
                  ))}
                </div>
              </div>

              {result && (
                <div className="text-center">
                  <h2 className="text-xl font-semibold text-slate-700 mb-4">Classification Complete</h2>
                  <div
                    className="inline-block bg-blue-100 text-blue-900 px-5 py-4 rounded-lg text-lg font-semibold"
                    dangerouslySetInnerHTML={{ __html: result.html }}
                  />
                  <div className="mt-8 flex gap-3 justify-center">
                    <button onClick={backOne} className="px-4 py-2 text-slate-700 hover:text-slate-900">
                      ← Back
                    </button>
                    <button onClick={reset} className="px-4 py-2 rounded bg-slate-700 text-white hover:bg-slate-800">
                      Start Over
                    </button>
                  </div>
                </div>
              )}

              {!result && currentNode && (
                <div>
                  <h2
                    className="text-xl font-semibold text-slate-800 mb-6 text-center"
                    dangerouslySetInnerHTML={{ __html: currentNode.questionHtml }}
                  />

                  <div className="space-y-3">
                    {currentNode.options.map((opt, idx) => (
                      <button
                        key={idx}
                        onClick={() => choose(idx)}
                        className="w-full bg-white border-2 border-slate-300 rounded-lg p-4 hover:border-blue-500 hover:bg-blue-50 transition-all text-left"
                      >
                        <div className="flex items-start gap-4">
                          <div className="w-24 h-24 bg-slate-100 rounded flex-shrink-0 flex items-center justify-center overflow-hidden">
                            {opt.imageSrc ? (
                              <img src={opt.imageSrc} alt={opt.label} className="w-full h-full object-contain" />
                            ) : opt.imageTag ? (
                              <span
                                className="w-full h-full flex items-center justify-center"
                                dangerouslySetInnerHTML={{ __html: opt.imageTag }}
                              />
                            ) : (
                              <span className="text-slate-400 text-xs">No image</span>
                            )}
                          </div>

                          <div className="min-w-0">
                            <div
                              className="text-lg font-semibold text-slate-800"
                              dangerouslySetInnerHTML={{ __html: opt.titleHtml || opt.label }}
                            />
                            {opt.contextHtml && (
                              <div
                                className="mt-1 text-sm text-slate-600"
                                dangerouslySetInnerHTML={{ __html: opt.contextHtml }}
                              />
                            )}
                          </div>
                        </div>
                      </button>
                    ))}
                  </div>

                  <div className="mt-8 flex gap-3">
                    <button
                      onClick={backOne}
                      disabled={path.length === 0}
                      className={`px-4 py-2 ${path.length === 0 ? "text-slate-300 cursor-not-allowed" : "text-slate-700 hover:text-slate-900"}`}
                    >
                      ← Back
                    </button>
                    <button onClick={reset} className="ml-auto px-4 py-2 text-slate-700 hover:text-slate-900">
                      Start Over
                    </button>
                  </div>
                </div>
              )}

              {!result && !currentNode && (
                <div className="text-center">
                  <div className="text-red-600 mb-4">Could not render this step.</div>
                  <div className="flex gap-3 justify-center">
                    <button onClick={backOne} className="px-4 py-2 text-slate-700 hover:text-slate-900">← Back</button>
                    <button onClick={reset} className="px-4 py-2 rounded bg-slate-700 text-white hover:bg-slate-800">Start Over</button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      );
    }

    ReactDOM.createRoot(document.getElementById("root")).render(<ClassificationGuide />);
  </script>
</body>
</html>
"""
    return (
        template
        .replace("__APP_NAME_ESC__", app_name)
        .replace("__APP_NAME_JSON__", json.dumps(app_name, ensure_ascii=False))
        .replace("__TREE_JSON__", tree_json)
    )


def validate_input(path_str: str) -> Path:
    p = Path(path_str).expanduser().resolve()
    if not p.exists():
        raise FileNotFoundError(f"Input file not found: {p}")
    if p.suffix.lower() not in {".mmd", ".mermaid"}:
        raise ValueError("Input must be .mmd or .mermaid")
    return p


def normalize_output(path_str: str) -> Path:
    p = Path(path_str).expanduser().resolve()
    if p.suffix.lower() != ".html":
        p = p.with_suffix(".html")
    return p


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert Mermaid flowchart to click-through HTML.")
    parser.add_argument("--input-mmd", required=True, help="Path to .mmd/.mermaid")
    parser.add_argument("--output-html", required=True, help="Output .html")
    parser.add_argument("--app-name", default="Classification Guide", help="UI title")
    args = parser.parse_args()

    try:
        in_path = validate_input(args.input_mmd)
        out_path = normalize_output(args.output_html)

        text = in_path.read_text(encoding="utf-8")
        g = parse_mermaid(text)

        if not g.nodes_in_order:
            raise ValueError("No nodes parsed from Mermaid file.")

        cycle = detect_cycle(g)
        if cycle:
            print("⚠️ Cycle detected: " + " -> ".join(cycle), file=sys.stderr)
            print("⚠️ Aborting. Click-through requires an acyclic decision graph.", file=sys.stderr)
            sys.exit(1)

        tree = build_tree(g)
        html = make_html(tree, args.app_name)
        out_path.write_text(html, encoding="utf-8")

        roots = top_nodes(g)
        print(f"✅ Wrote: {out_path}")
        if len(roots) == 1:
            print(f"ℹ️ Root: {roots[0]}")
        else:
            print(f"ℹ️ Multiple roots ({len(roots)}): synthetic start used.")

    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
