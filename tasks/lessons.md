# FinClose AI — Lessons & Self-Improvement Log
## Updated by Claude Code after every correction | Format: [tag] Root cause → Fix pattern

---

## Session 1 — Data Generation + Agent Layer
*Built with Claude (chat interface) — March 2026*

### Lesson 001 [logic]
**Root cause:** `for code, info in coa_dict:` fails — dict iteration yields keys only, not (key, value) pairs.
**Fix pattern:** Always use `coa_dict.items()` when you need both key and value. Never assume dict unpacks like a list of tuples.

### Lesson 002 [context]
**Root cause:** DB path in `db_tools.py` was relative to the wrong working directory.
**Fix pattern:** Always use `os.path.dirname(__file__)` as anchor for relative paths inside modules. Never assume CWD.

### Lesson 003 [planning]
**Root cause:** BitNet b1.58 was suggested as the LLM backend but doesn't run well on 8GB unified RAM in practice.
**Fix pattern:** For memory-constrained hardware (≤8GB), default to Ollama + Mistral 7B Q4 (~4.5GB). BitNet is experimental — don't promise it in demos.

### Lesson 004 [tool-use]
**Root cause:** ChromaDB + sentence-transformers couldn't install due to disk space in the build environment.
**Fix pattern:** Always check available disk/RAM before installing heavy deps. Fall back to full-text policy injection (what we did) as a viable RAG alternative that's simpler and more auditable anyway.

### Lesson 005 [logic]
**Root cause:** LangGraph requires state as `dict` or `TypedDict` at graph boundaries — our `AgentState` dataclass needed a wrapper.
**Fix pattern:** Use a thin `GraphState` TypedDict wrapper that holds the dataclass as a field. The dataclass stays clean; the graph gets its dict.

---

## Active Rules (derived from above)

1. Always use `.items()` on dicts when iterating for key+value
2. Anchor all file paths to `__file__`, never CWD
3. Default LLM: Mistral 7B Q4 via Ollama for ≤8GB RAM hardware
4. Wrap AgentState in a TypedDict for LangGraph boundary compatibility
5. Policy RAG via full-text injection is acceptable and more auditable than vector search for ≤10 documents

---

## Open Questions / Next Session Picks Up Here

- [ ] Streamlit UI: does `st.status()` work well for streaming agent progress steps?
- [ ] FastAPI: should the `/run` endpoint be async to avoid blocking on Ollama?
- [ ] Eval: what's the right ground truth format for variance analysis (exact numbers vs. range)?
- [ ] Monitoring: Prometheus vs simple JSON metrics file for a portfolio demo?
