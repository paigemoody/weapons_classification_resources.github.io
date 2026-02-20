"""
Convert a Mermaid flowchart into a "hypothesis filtering" HTML guide.

What this UI is (and why)
-------------------------
This generator reuses the SAME Mermaid decision tree (.mmd) but produces a different
experience than the click-through "start at the top" guide.

Instead of forcing a single path from the root, this UI:
- Lets a user start anywhere (menu-based question list)
- Lets the user skip any question ("I don't know" = no constraint)
- Filters down to a short ranked list of leaf hypotheses as the user answers
- Prevents contradictions by refusing any selection that would eliminate all hypotheses

Key assumptions (match your constraints)
----------------------------------------
- The Mermaid graph is a TREE (or forest with a synthetic root) with no cycles.
- Leaves are "classification outcomes".
- One answer per question (no multi-select for now).
- "I don't know" = skip (later you can add "help me figure it out" per node).

Usage
-----
python3 src/mermaid_to_hypothesis_filtering.py \
  --input-mmd weapons-classification-flowchart.mmd \
  --output-html classification-guide-hypothesis-filtering.html \
  --app-name "[DEMO] Weapons Classification Guide (Hypothesis Filtering)"
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Set


# -----------------------------
# Mermaid parsing helpers
# -----------------------------

# Edge formats supported:
#   A --> B
#   A --> |Label| B
#   A --> |"Label with HTML"| B
EDGE_RE = re.compile(
    r"""^\s*([A-Za-z0-9_]+)\s*-->\s*(?:\|((?:"[^"]*"|[^|])*)\|\s*)?([A-Za-z0-9_]+)\s*$""",
    re.DOTALL,
)

# Node format:
#   NodeId["Some <br/> Label"]
NODE_RE = re.compile(
    r'^\s*([A-Za-z0-9_]+)\s*\[\s*"([\s\S]*?)"\s*\]\s*$',
    re.DOTALL,
)

IMG_TAG_RE = re.compile(r"<img\b[^>]*>", re.IGNORECASE | re.DOTALL)
SRC_RE = re.compile(r"""src\s*=\s*(['"])(.*?)\1""", re.IGNORECASE | re.DOTALL)
H1_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.IGNORECASE | re.DOTALL)
P_RE = re.compile(r"<p[^>]*>(.*?)</p>", re.IGNORECASE | re.DOTALL)


def extract_first_img_tag(html: str) -> Optional[str]:
    m = IMG_TAG_RE.search(html or "")
    return m.group(0) if m else None


def extract_img_src(img_tag: str) -> str:
    m = SRC_RE.search(img_tag or "")
    return m.group(2).strip() if m else ""


def strip_img_tags(html: str) -> str:
    return re.sub(r"<img\b[^>]*>", "", html or "", flags=re.IGNORECASE | re.DOTALL).strip()


def mmd_label_to_html(raw: str) -> str:
    """
    Keep HTML formatting and basic markdown-bold conversion.
    - Converts '**x**' -> '<strong>x</strong>'
    - Leaves <img>, <br>, and other HTML intact
    """
    txt = (raw or "").strip()
    txt = txt.replace('\\"', '"')  # unescape \" inside quoted labels
    txt = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", txt, flags=re.DOTALL)
    return txt


def strip_html_for_plain(text: str) -> str:
    """Create a plain text fallback from html-ish label."""
    t = re.sub(r"<br\s*/?>", " ", text or "", flags=re.IGNORECASE)
    t = re.sub(r"<[^>]+>", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def fallback_label(node_id: str) -> str:
    return node_id.replace("_", " ")


def parse_edge_label(edge_html: str, fallback_text: str) -> Dict[str, str]:
    """
    Parse edge label into:
      - titleHtml: option title markup
      - contextHtml: optional supporting <p> blocks
      - plainLabel: fallback plain text
      - edgeImageTag / edgeImageSrc: optional image from edge label

    Rules:
      - If <h1> exists, title is first <h1> content
      - context is concatenated <p> blocks
      - otherwise title is whole edge label (minus <img>)
    """
    html = mmd_label_to_html(edge_html or "")

    edge_img_tag = extract_first_img_tag(html) or ""
    edge_img_src = extract_img_src(edge_img_tag) if edge_img_tag else ""

    html_wo_img = strip_img_tags(html)

    if not html_wo_img:
        plain = strip_html_for_plain(fallback_text) or fallback_text
        return {
            "titleHtml": plain,
            "contextHtml": "",
            "plainLabel": plain,
            "edgeImageTag": edge_img_tag,
            "edgeImageSrc": edge_img_src,
        }

    h1_match = H1_RE.search(html_wo_img)
    p_matches = P_RE.findall(html_wo_img)

    title_html = h1_match.group(1).strip() if h1_match else html_wo_img.strip()

    context_html = ""
    if p_matches:
        context_html = "".join(f"<p>{p.strip()}</p>" for p in p_matches)

    plain = strip_html_for_plain(title_html) or strip_html_for_plain(html_wo_img) or fallback_text

    return {
        "titleHtml": title_html,
        "contextHtml": context_html,
        "plainLabel": plain,
        "edgeImageTag": edge_img_tag,
        "edgeImageSrc": edge_img_src,
    }


class Graph:
    def __init__(self) -> None:
        self.node_html: Dict[str, str] = {}                # node_id -> html label
        self.children: Dict[str, List[str]] = {}           # node_id -> [child_ids in file order]
        self.edge_label: Dict[Tuple[str, str], str] = {}   # (src,dst) -> raw html label
        self.indegree: Dict[str, int] = {}
        self.nodes_in_order: List[str] = []                # first-seen order

    def ensure_node(self, nid: str) -> None:
        if nid not in self.children:
            self.children[nid] = []
        if nid not in self.indegree:
            self.indegree[nid] = 0
        if nid not in self.node_html:
            self.node_html[nid] = fallback_label(nid)
        if nid not in self.nodes_in_order:
            self.nodes_in_order.append(nid)

    def add_node_label(self, nid: str, raw_label: str) -> None:
        self.ensure_node(nid)
        self.node_html[nid] = mmd_label_to_html(raw_label)

    def add_edge(self, src: str, dst: str, lbl: Optional[str]) -> None:
        self.ensure_node(src)
        self.ensure_node(dst)
        self.children[src].append(dst)
        self.indegree[dst] += 1
        if lbl is not None:
            cleaned = lbl.strip()
            # strip wrapping quotes if edge was |"..."|
            if len(cleaned) >= 2 and cleaned[0] == '"' and cleaned[-1] == '"':
                cleaned = cleaned[1:-1]
            self.edge_label[(src, dst)] = mmd_label_to_html(cleaned)


def parse_mermaid(text: str) -> Graph:
    g = Graph()

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        s = line.strip()

        if not s:
            continue
        if s.startswith("%%"):
            continue
        if s.startswith("flowchart"):
            continue

        m_node = NODE_RE.match(line)
        if m_node:
            nid, raw = m_node.groups()
            g.add_node_label(nid, raw)
            continue

        m_edge = EDGE_RE.match(line)
        if m_edge:
            src, edge_lbl, dst = m_edge.groups()
            g.add_edge(src, dst, edge_lbl)
            continue

    return g


def detect_cycle(g: Graph) -> Optional[List[str]]:
    """
    DFS cycle detection.
    Returns one cycle path if found, else None.
    """
    WHITE, GRAY, BLACK = 0, 1, 2
    color: Dict[str, int] = {n: WHITE for n in g.children}
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


# -----------------------------
# Hypothesis filtering model
# -----------------------------

@dataclass(frozen=True)
class Option:
    option_id: str          # stable id (src->dst)
    src: str
    dst: str
    title_html: str
    context_html: str
    plain_label: str
    image_src: str


@dataclass
class Question:
    node_id: str
    question_html: str
    question_text: str
    # One question = one node with children; each outgoing edge is an "option"
    options: List[Option]


def build_questions(g: Graph) -> Dict[str, Question]:
    """
    Convert each internal node (node with children) into a "question"
    that the UI can show in a menu.
    """
    out: Dict[str, Question] = {}

    for nid in g.nodes_in_order:
        kids = g.children.get(nid, [])
        if not kids:
            continue  # leaves are outcomes, not questions

        q_html = g.node_html.get(nid, fallback_label(nid))
        q = Question(
            node_id=nid,
            question_html=q_html,
            question_text=strip_html_for_plain(q_html) or fallback_label(nid),
            options=[],
        )

        for child in kids:
            child_html = g.node_html.get(child, fallback_label(child))

            raw_edge_html = g.edge_label.get((nid, child), "")
            edge_parts = parse_edge_label(raw_edge_html, fallback_text=strip_html_for_plain(child_html))

            # Option image precedence:
            # - edge label image first (more specific),
            # - else destination node image.
            edge_img_src = edge_parts["edgeImageSrc"] or ""
            node_img_tag = extract_first_img_tag(child_html) or ""
            node_img_src = extract_img_src(node_img_tag) if node_img_tag else ""
            final_img_src = edge_img_src or node_img_src

            q.options.append(
                Option(
                    option_id=f"{nid}__TO__{child}",
                    src=nid,
                    dst=child,
                    title_html=edge_parts["titleHtml"] or strip_html_for_plain(child_html) or fallback_label(child),
                    context_html=edge_parts["contextHtml"] or "",
                    plain_label=edge_parts["plainLabel"] or strip_html_for_plain(child_html) or fallback_label(child),
                    image_src=final_img_src,
                )
            )

        out[nid] = q

    return out


def find_leaves(g: Graph) -> List[str]:
    return [n for n in g.nodes_in_order if not g.children.get(n)]


def compute_depths(g: Graph, roots: List[str]) -> Dict[str, int]:
    """
    Depth is used only for ranking (deeper leaves are "more specific").
    For a true tree, depth is unique; for a forest or DAG-ish input, we take min depth.
    """
    depth: Dict[str, int] = {n: 10**9 for n in g.nodes_in_order}
    stack: List[Tuple[str, int]] = [(r, 0) for r in roots]

    while stack:
        nid, d = stack.pop()
        if d >= depth.get(nid, 10**9):
            continue
        depth[nid] = d
        for child in g.children.get(nid, []):
            stack.append((child, d + 1))

    # Fill anything unreachable with 0 just so ranking doesn't explode
    for n in g.nodes_in_order:
        if depth[n] == 10**9:
            depth[n] = 0
    return depth


def compute_leaf_sets(g: Graph, leaves: List[str]) -> Dict[str, Set[str]]:
    """
    For every node, compute the set of leaf outcomes in its subtree.

    This makes filtering easy:
      choosing option (node -> child) means "candidates must be in leaf_set[child]".
    """
    leaf_set: Dict[str, Set[str]] = {n: set() for n in g.nodes_in_order}

    # Post-order traversal via recursion is fine for your current tree sizes,
    # but we implement an iterative topo-ish approach to be safer.
    # Since it's a tree, we can just compute from leaves upward by repeated passes.
    leaf_lookup = set(leaves)
    for lf in leaves:
        leaf_set[lf].add(lf)

    # Repeat until no changes (tree converges quickly).
    changed = True
    while changed:
        changed = False
        for n in g.nodes_in_order[::-1]:
            kids = g.children.get(n, [])
            if not kids:
                continue
            union: Set[str] = set()
            for c in kids:
                union |= leaf_set.get(c, set())
            if union and union != leaf_set[n]:
                leaf_set[n] = union
                changed = True

    return leaf_set


def make_model(g: Graph) -> dict:
    """
    Build a JSON model for the browser:
    - questions list (menu)
    - leaf outcomes (for results)
    - mapping: option_id -> leaf set of that option's dst subtree
    """
    roots = top_nodes(g)
    if not roots:
        raise ValueError("No top-level node detected (no in-degree-0 nodes found).")

    questions = build_questions(g)
    leaves = find_leaves(g)
    depths = compute_depths(g, roots)
    leaf_sets = compute_leaf_sets(g, leaves)

    # Questions in menu order:
    # - Keep Mermaid file order, but drop leaves.
    question_ids = [nid for nid in g.nodes_in_order if nid in questions]

    # Model: question objects
    q_objs: List[dict] = []
    option_to_leafset: Dict[str, List[str]] = {}

    for qid in question_ids:
        q = questions[qid]
        opt_objs: List[dict] = []
        for opt in q.options:
            opt_objs.append(
                {
                    "optionId": opt.option_id,
                    "dstNodeId": opt.dst,
                    "titleHtml": opt.title_html,
                    "contextHtml": opt.context_html,
                    "plainLabel": opt.plain_label,
                    "imageSrc": opt.image_src,
                }
            )
            option_to_leafset[opt.option_id] = sorted(list(leaf_sets.get(opt.dst, set())))

        q_objs.append(
            {
                "nodeId": q.node_id,
                "questionHtml": q.question_html,
                "questionText": q.question_text,
                "options": opt_objs,
            }
        )

    # Leaf objects for displaying hypotheses (use the node label as the "result card" content)
    leaf_objs: List[dict] = []
    for lf in leaves:
        lf_html = g.node_html.get(lf, fallback_label(lf))
        leaf_objs.append(
            {
                "leafId": lf,
                "leafHtml": lf_html,
                "leafText": strip_html_for_plain(lf_html) or fallback_label(lf),
                "depth": depths.get(lf, 0),
            }
        )

    # Start candidate set = all leaves under ALL roots (forest-safe)
    all_candidates: Set[str] = set()
    for r in roots:
        all_candidates |= leaf_sets.get(r, set())
    if not all_candidates:
        # fallback
        all_candidates = set(leaves)

    return {
        "roots": roots,
        "questions": q_objs,
        "leaves": leaf_objs,
        "optionToLeafIds": option_to_leafset,
        "initialCandidates": sorted(list(all_candidates)),
    }


# -----------------------------
# HTML generator (React)
# -----------------------------

def make_html(model: dict, app_name: str) -> str:
    model_json = json.dumps(model, ensure_ascii=False, indent=2)

    template = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>__APP_NAME_ESC__</title>

  <!-- React (no build step) -->
  <script crossorigin src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
  <script crossorigin src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>

  <!-- Babel for JSX in-browser (fine for a static demo; you can remove later if you build) -->
  <script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>

  <!-- Tailwind via CDN -->
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-50">
  <div id="root"></div>

  <script type="text/babel">
    const { useEffect, useMemo, useState } = React;

    const APP_NAME = __APP_NAME_JSON__;
    const MODEL = __MODEL_JSON__;

    // Utility: intersection of two arrays of strings (small sizes; keep simple)
    function intersect(a, b) {
      const setB = new Set(b);
      return a.filter(x => setB.has(x));
    }

    // Utility: stable sorting by depth desc, then label asc
    function sortHypotheses(hyps) {
      return [...hyps].sort((x, y) => {
        if (y.depth !== x.depth) return y.depth - x.depth; // deeper = more specific
        return (x.leafText || "").localeCompare(y.leafText || "");
      });
    }

    function App() {
      // Which menu item (question) is currently open
      const [activeQuestionId, setActiveQuestionId] = useState(MODEL.questions[0]?.nodeId || null);

      // Selections: nodeId -> optionId
      // (Skipping a question = no entry for that nodeId.)
      const [answers, setAnswers] = useState({});

      // For polite UI: if the user tries a contradictory choice, show an explanation
      const [errorMsg, setErrorMsg] = useState("");

      // Derived: current candidate leaves after applying all answers as hard constraints
      const candidates = useMemo(() => {
        let cur = MODEL.initialCandidates;
        for (const [nodeId, optionId] of Object.entries(answers)) {
          const allowed = MODEL.optionToLeafIds[optionId] || [];
          cur = intersect(cur, allowed);
        }
        return cur;
      }, [answers]);

      // Derived: map leafId -> leaf object for display
      const leafById = useMemo(() => {
        const m = new Map();
        for (const lf of MODEL.leaves) m.set(lf.leafId, lf);
        return m;
      }, []);

      // Derived: ranked hypotheses
      const rankedHypotheses = useMemo(() => {
        const hyps = candidates
          .map(id => leafById.get(id))
          .filter(Boolean);
        return sortHypotheses(hyps);
      }, [candidates, leafById]);

      // Derived: show only top N hypotheses (your "short ranked list")
      const TOP_N = 5;
      const topHypotheses = rankedHypotheses.slice(0, TOP_N);

      // Derived: for each question, is it still "compatible" with current candidates?
      // We use this to:
      // - gray out questions that cannot affect the result anymore (optional)
      // - or show a small badge ("already implied" etc.) later if you want
      const questionMeta = useMemo(() => {
        const meta = new Map();

        for (const q of MODEL.questions) {
          // Union of candidates that match ANY option for this question:
          // if union == candidates, then the question doesn't narrow anything right now.
          let union = [];
          const seen = new Set();
          for (const opt of q.options) {
            const allowed = MODEL.optionToLeafIds[opt.optionId] || [];
            for (const id of intersect(candidates, allowed)) {
              if (!seen.has(id)) {
                seen.add(id);
                union.push(id);
              }
            }
          }
          const canNarrow = union.length > 0 && union.length < candidates.length;
          const isRelevant = union.length > 0; // if 0, the question is fully incompatible with current candidates
          meta.set(q.nodeId, { canNarrow, isRelevant });
        }
        return meta;
      }, [candidates]);

      // When the active question becomes irrelevant (due to answers), auto-jump to the next relevant one
      useEffect(() => {
        if (!activeQuestionId) return;
        const meta = questionMeta.get(activeQuestionId);
        if (meta && meta.isRelevant) return;

        const next = MODEL.questions.find(q => (questionMeta.get(q.nodeId)?.isRelevant));
        if (next) setActiveQuestionId(next.nodeId);
      }, [activeQuestionId, questionMeta]);

      const resetAll = () => {
        setAnswers({});
        setErrorMsg("");
        setActiveQuestionId(MODEL.questions[0]?.nodeId || null);
      };

      const skipQuestion = (nodeId) => {
        setErrorMsg("");
        setAnswers(prev => {
          const next = { ...prev };
          delete next[nodeId];
          return next;
        });
      };

      // Try to set an answer; refuse if it would eliminate all candidates
      const chooseOption = (nodeId, optionId) => {
        setErrorMsg("");

        // Compute what candidates would be if we applied this answer
        let cur = MODEL.initialCandidates;

        for (const [nid, oid] of Object.entries({ ...answers, [nodeId]: optionId })) {
          const allowed = MODEL.optionToLeafIds[oid] || [];
          cur = intersect(cur, allowed);
        }

        if (cur.length === 0) {
          setErrorMsg("That choice conflicts with earlier answers. Try a different option, or remove a previous answer.");
          return;
        }

        setAnswers(prev => ({ ...prev, [nodeId]: optionId }));
      };

      const removeAnswer = (nodeId) => {
        skipQuestion(nodeId);
      };

      const activeQuestion = useMemo(
        () => MODEL.questions.find(q => q.nodeId === activeQuestionId) || null,
        [activeQuestionId]
      );

      // For the "Your answers" panel: show question + selected option label
      const answerChips = useMemo(() => {
        const chips = [];
        for (const q of MODEL.questions) {
          const optId = answers[q.nodeId];
          if (!optId) continue;
          const opt = q.options.find(o => o.optionId === optId);
          chips.push({
            nodeId: q.nodeId,
            questionText: q.questionText,
            optionLabel: opt?.plainLabel || "Selected",
          });
        }
        return chips;
      }, [answers]);

      return (
        <div className="min-h-screen p-5 md:p-8">
          <div className="max-w-6xl mx-auto">

            {/* Header */}
            <div className="mb-6">
              <h1 className="text-2xl md:text-3xl font-bold text-slate-900">{APP_NAME}</h1>
              <p className="text-slate-600 mt-2 max-w-3xl">
                Start anywhere. Answer only what you can tell. Each answer narrows down a ranked list of likely classifications.
              </p>
            </div>

            {/* Error banner (for contradiction attempts) */}
            {errorMsg && (
              <div className="mb-5 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-red-800">
                {errorMsg}
              </div>
            )}

            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">

              {/* Left: Question menu */}
              <div className="lg:col-span-4">
                <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
                  <div className="px-4 py-3 border-b border-slate-200 flex items-center justify-between">
                    <div className="font-semibold text-slate-800">Questions</div>
                    <button
                      onClick={resetAll}
                      className="text-sm text-slate-600 hover:text-slate-900"
                      title="Clear all answers"
                    >
                      Reset
                    </button>
                  </div>

                  <div className="max-h-[70vh] overflow-auto">
                    {MODEL.questions.map((q) => {
                      const selected = !!answers[q.nodeId];
                      const meta = questionMeta.get(q.nodeId) || { canNarrow: true, isRelevant: true };
                      const isActive = q.nodeId === activeQuestionId;

                      // We don't hard-disable irrelevant questions (people might want to explore),
                      // but we visually deemphasize them.
                      const rowClass = [
                        "px-4 py-3 border-b border-slate-100 cursor-pointer",
                        isActive ? "bg-blue-50" : "bg-white hover:bg-slate-50",
                        !meta.isRelevant ? "opacity-50" : "",
                      ].join(" ");

                      return (
                        <div
                          key={q.nodeId}
                          className={rowClass}
                          onClick={() => setActiveQuestionId(q.nodeId)}
                        >
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0">
                              <div className="text-sm font-medium text-slate-900 truncate">
                                {q.questionText || q.nodeId}
                              </div>

                              <div className="mt-1 flex items-center gap-2">
                                {selected ? (
                                  <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800">
                                    Answered
                                  </span>
                                ) : (
                                  <span className="text-xs px-2 py-0.5 rounded-full bg-slate-100 text-slate-700">
                                    Unanswered
                                  </span>
                                )}

                                {meta.canNarrow ? (
                                  <span className="text-xs px-2 py-0.5 rounded-full bg-blue-100 text-blue-800">
                                    Can narrow
                                  </span>
                                ) : (
                                  <span className="text-xs px-2 py-0.5 rounded-full bg-slate-100 text-slate-600">
                                    Won't narrow
                                  </span>
                                )}
                              </div>
                            </div>

                            {selected && (
                              <button
                                className="text-xs text-slate-600 hover:text-slate-900"
                                onClick={(e) => { e.stopPropagation(); removeAnswer(q.nodeId); }}
                                title="Remove this answer"
                              >
                                Remove
                              </button>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Answers summary */}
                <div className="mt-4 bg-white rounded-xl shadow-sm border border-slate-200 p-4">
                  <div className="font-semibold text-slate-800 mb-2">Your answers</div>

                  {answerChips.length === 0 ? (
                    <div className="text-sm text-slate-600">No answers yet. Pick any question to start.</div>
                  ) : (
                    <div className="flex flex-wrap gap-2">
                      {answerChips.map((a) => (
                        <button
                          key={a.nodeId}
                          onClick={() => setActiveQuestionId(a.nodeId)}
                          className="text-left text-xs px-3 py-2 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-800"
                          title={a.questionText}
                        >
                          <div className="font-semibold">{a.optionLabel}</div>
                          <div className="text-slate-600 truncate max-w-[14rem]">{a.questionText}</div>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              {/* Center: Active question */}
              <div className="lg:col-span-5">
                <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5 md:p-6">
                  {!activeQuestion ? (
                    <div className="text-slate-700">No question selected.</div>
                  ) : (
                    <div>
                      <div
                        className="prose max-w-none"
                        dangerouslySetInnerHTML={{ __html: activeQuestion.questionHtml }}
                      />

                      <div className="mt-5 space-y-3">
                        {activeQuestion.options.map((opt) => {
                          const isSelected = answers[activeQuestion.nodeId] === opt.optionId;

                          return (
                            <button
                              key={opt.optionId}
                              onClick={() => chooseOption(activeQuestion.nodeId, opt.optionId)}
                              className={[
                                "w-full text-left rounded-xl border p-4 transition",
                                isSelected
                                  ? "border-blue-500 bg-blue-50"
                                  : "border-slate-200 hover:border-blue-400 hover:bg-slate-50"
                              ].join(" ")}
                            >
                              <div className="flex gap-4 items-start">
                                <div className="w-24 h-24 bg-slate-100 rounded-lg flex items-center justify-center overflow-hidden flex-shrink-0">
                                  {opt.imageSrc ? (
                                    <img
                                      src={opt.imageSrc}
                                      alt={opt.plainLabel || "Option image"}
                                      className="w-full h-full object-contain"
                                    />
                                  ) : (
                                    <span className="text-xs text-slate-400 px-2 text-center">No image</span>
                                  )}
                                </div>

                                <div className="min-w-0">
                                  <div
                                    className="text-lg font-semibold text-slate-900"
                                    dangerouslySetInnerHTML={{ __html: opt.titleHtml || opt.plainLabel || "Option" }}
                                  />
                                  {opt.contextHtml && (
                                    <div
                                      className="mt-1 text-sm text-slate-700"
                                      dangerouslySetInnerHTML={{ __html: opt.contextHtml }}
                                    />
                                  )}
                                </div>
                              </div>
                            </button>
                          );
                        })}
                      </div>

                      {/* Skip control: remove answer for this question */}
                      <div className="mt-5 flex items-center gap-3">
                        <button
                          onClick={() => skipQuestion(activeQuestion.nodeId)}
                          className="px-4 py-2 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-800"
                        >
                          I don't know / skip
                        </button>

                        {answers[activeQuestion.nodeId] && (
                          <span className="text-sm text-slate-600">
                            You can also remove your answer from the menu on the left.
                          </span>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* Right: Hypotheses */}
              <div className="lg:col-span-3">
                <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
                  <div className="px-4 py-3 border-b border-slate-200">
                    <div className="font-semibold text-slate-800">Hypotheses</div>
                    <div className="text-sm text-slate-600 mt-1">
                      {candidates.length} possible outcome{candidates.length === 1 ? "" : "s"} remaining
                    </div>
                  </div>

                  <div className="p-4 space-y-3">
                    {topHypotheses.length === 0 ? (
                      <div className="text-sm text-slate-700">
                        No hypotheses remain. (This shouldn't happen because we block contradictions.)
                      </div>
                    ) : (
                      topHypotheses.map((h, idx) => (
                        <div
                          key={h.leafId}
                          className="rounded-xl border border-slate-200 bg-slate-50 p-3"
                        >
                          <div className="flex items-center justify-between">
                            <div className="text-xs font-semibold text-slate-600">
                              Rank #{idx + 1}
                            </div>
                            <div className="text-xs text-slate-500">
                              Specificity: {h.depth}
                            </div>
                          </div>
                          <div
                            className="mt-2 text-sm font-semibold text-slate-900"
                            dangerouslySetInnerHTML={{ __html: h.leafHtml }}
                          />
                        </div>
                      ))
                    )}

                    {rankedHypotheses.length > TOP_N && (
                      <div className="text-xs text-slate-600">
                        Showing top {TOP_N} of {rankedHypotheses.length}.
                      </div>
                    )}
                  </div>
                </div>

                <div className="mt-4 text-xs text-slate-500">
                  Ranking currently prefers more specific (deeper) leaf categories.
                  If you want a different ranking later (e.g., likelihood weights), we can add it.
                </div>
              </div>

            </div>
          </div>
        </div>
      );
    }

    const root = ReactDOM.createRoot(document.getElementById("root"));
    root.render(<App />);
  </script>
</body>
</html>
"""
    return (
        template
        .replace("__APP_NAME_ESC__", app_name)
        .replace("__APP_NAME_JSON__", json.dumps(app_name, ensure_ascii=False))
        .replace("__MODEL_JSON__", model_json)
    )


# -----------------------------
# CLI + I/O
# -----------------------------

def ensure_output_html(path_str: str) -> Path:
    p = Path(path_str)
    if p.suffix.lower() != ".html":
        p = p.with_suffix(".html")
    return p


def validate_input_path(path_str: str) -> Path:
    p = Path(path_str)
    if not p.exists():
        raise FileNotFoundError(f"Input file not found: {p}")
    if p.suffix.lower() not in {".mmd", ".mermaid"}:
        raise ValueError("Input must be a .mmd or .mermaid file")
    return p


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert Mermaid flowchart to a hypothesis-filtering HTML guide."
    )
    parser.add_argument("--input-mmd", required=True, help="Path to .mmd or .mermaid file")
    parser.add_argument("--output-html", required=True, help="Output HTML path")
    parser.add_argument("--app-name", default="Classification Guide (Hypothesis Filtering)", help="UI title")
    args = parser.parse_args()

    try:
        in_path = validate_input_path(args.input_mmd)
        out_path = ensure_output_html(args.output_html)

        text = in_path.read_text(encoding="utf-8")
        g = parse_mermaid(text)

        if not g.nodes_in_order:
            raise ValueError("No Mermaid nodes were parsed from input file.")

        cycle = detect_cycle(g)
        if cycle:
            cycle_str = " -> ".join(cycle)
            print(f"⚠️  Cycle detected in Mermaid chart: {cycle_str}", file=sys.stderr)
            print("⚠️  Aborting. Hypothesis filtering requires an acyclic decision flow.", file=sys.stderr)
            sys.exit(1)

        model = make_model(g)
        html = make_html(model, args.app_name)

        out_path.write_text(html, encoding="utf-8")
        print(f"✅ Wrote: {out_path}")

        roots = top_nodes(g)
        if len(roots) > 1:
            print(f"ℹ️  Multiple top nodes detected ({len(roots)}). This UI can still work (menu-based).")
        else:
            print(f"ℹ️  Root detected: {roots[0]}")

        print(f"ℹ️  Questions: {len(model['questions'])}, Leaves (hypotheses): {len(model['leaves'])}")

    except Exception as exc:
        print(f"❌ Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()