import sys
import os
import json
import time
import subprocess
from pathlib import Path

# Add plugins dir to path to import RAG scripts directly
root_dir = os.path.dirname(os.path.dirname(__file__))
sys.path.append(root_dir)
from dotenv import load_dotenv
load_dotenv(os.path.join(root_dir, ".env"))

from src.lib.index import unified_rag_search

def run_rg(query: str) -> dict:
    start = time.time()
    try:
        cmd = ["rg", "-n", query, "skills", "src", "docs"]
        output = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL)
        lines = output.strip().split('\n')
        end = time.time()
        return {
            "success": True,
            "count": len(lines),
            "head": "\n".join(lines[:10]),
            "time_ms": int((end - start) * 1000)
        }
    except subprocess.CalledProcessError:
        end = time.time()
        return {
            "success": False,
            "count": 0,
            "head": "No hits.",
            "time_ms": int((end - start) * 1000)
        }

def run_rag(query: str) -> dict:
    start = time.time()
    res_str = unified_rag_search({"query": query})
    res = json.loads(res_str)
    end = time.time()
    
    if "error" in res:
         return {
            "success": False,
            "count": 0,
            "head": res["error"],
            "time_ms": int((end - start) * 1000)
         }
         
    # Flatten the iteractive search sections to count hits
    results = res.get("results", [])
    total_hits = 0
    head_lines = []
    
    for section in results:
        t = section.get("type", "unknown")
        hits = section.get("hits", [])
        total_hits += len(hits)
        
        for h in hits:
            if "raw" in h:
                head_lines.append(f"[{t}] {h['raw']}")
            elif "file" in h:
                head_lines.append(f"[{t}] {h['file']}:{h['line']} {h.get('content', '')}")
                
    return {
        "success": True,
        "count": total_hits,
        "head": "\n".join(head_lines[:15]),
        "time_ms": int((end - start) * 1000)
    }

queries = [
    "extract_python_symbols",
    "how do i deploy the dashboard",
    "all mcp tools related to memory"
]

report = []

for idx, q in enumerate(queries):
    print(f"Executing Query {idx+1}: {q}")
    rg_res = run_rg(q)
    rag_res = run_rag(q)
    
    report.append(f"### Query {idx+1}: `{q}`\n")
    report.append(f"**Ripgrep (`rg`)**:\n- **Time**: {rg_res['time_ms']}ms\n- **Hits**: {rg_res['count']}\n- **Top Matches**:\n```\n{rg_res['head']}\n```\n")
    report.append(f"**Unified RAG Search**:\n- **Time**: {rag_res['time_ms']}ms\n- **Hits**: {rag_res['count']}\n- **Top Matches**:\n```\n{rag_res['head']}\n```\n")
    report.append("---\n")

output_path = Path(__file__).resolve().parents[1] / "output" / "test_report.md"
output_path.parent.mkdir(parents=True, exist_ok=True)
with open(output_path, "w") as f:
    f.write("# RAG vs RipGrep Native Search Evaluation\n\n" + "\n".join(report))

print(f"Report written to {output_path}")
