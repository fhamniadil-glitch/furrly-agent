## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- When graphify-out/graph.json exists, run `graphify query "<question>"` before your first grep, search or source-file read for a codebase question, and put this rule in every subagent prompt that explores code. Read raw files only for lines the graph or an earlier read already located. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
- A committed graphify-out/graph.json is rewritten whole on every build, so a large diff to it in a pull request is expected. Do not flag it as churn or suggest skipping the graph rebuild or its hooks.

## Token economy

- Gemini CLI (`gemini`) offloads bulk reading. For a file, PDF, log or web page over ~500 lines, run `gemini -p "<precise question>" < file` (or `cat a b | gemini -p ...`) and work from its answer instead of reading the whole thing. Do not send secrets or customer personal data to it. If `gemini` is missing or has no API key, fall back to normal reads.
- Read only the lines you need (offset/limit, `sed -n`), never whole large files "to be safe".
- Prefer one targeted command over several exploratory ones; do not re-read files already in context.
- Keep answers short (user preference: bref et efficace).
- Repetitive jobs (posting, replies, reports) belong in the GitHub Actions workflows or Zapier/Make, not in a chat.
- PAL MCP (`pal` server in `.mcp.json`) lets Claude hand work to Gemini: `chat` for a second opinion or bulk drafting, `consensus` to compare models, `clink` to run Gemini CLI as a sub-agent. Use it for heavy reading/drafting, not for small tasks. The real Gemini key is injected by the environment's network secret; the placeholder in `.mcp.json` is not a secret.
