"""
BrowseComp-Plus Tools for ECM Agent.

Implements search and document retrieval tools for BrowseComp-Plus.
Context management is handled by ctx_cli (scope, return, note, insight).

Mapping to FoldAgent:
- FoldAgent branch() → ctx_cli scope <name>
- FoldAgent return() → ctx_cli return -m "..."
- FoldAgent think() → ctx_cli note -m "..."
- FoldAgent finish() → ctx_cli return -m "ANSWER: ..."

Reference: https://github.com/sunnweiwei/FoldAgent/blob/main/agents/tool_spec.py
"""

from typing import Optional
import json


# Tool definitions for OpenAI function calling format
# Only search tools - context management via ctx_cli
BROWSECOMP_SEARCH_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search",
            "description": "Performs a search over the document corpus. Returns top results with document IDs, URLs, and content snippets.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query string"
                    },
                    "topk": {
                        "type": "integer",
                        "description": "Number of results to return (default: 5)",
                        "default": 5
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "open_page",
            "description": "Retrieves the complete content of a document by its ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "docid": {
                        "type": "string",
                        "description": "Document ID from search results"
                    }
                },
                "required": ["docid"]
            }
        }
    }
]


class BrowseCompToolExecutor:
    """
    Executes BrowseComp-Plus search tools against the document corpus.

    Provides simple keyword-based search over evidence documents
    (for fair comparison without external search infrastructure).

    Note: Context management (scope, return, note) is handled by ctx_cli,
    not by this executor.
    """

    def __init__(self, documents: list[dict] = None):
        """
        Initialize tool executor.

        Args:
            documents: List of documents with 'docid', 'text', 'url' fields
        """
        self.documents = documents or []
        self.doc_index = {doc.get('docid', str(i)): doc for i, doc in enumerate(self.documents)}

    def load_documents(self, evidence_docs: list[dict], gold_docs: list[dict] = None):
        """Load documents for a specific task."""
        all_docs = list(evidence_docs)
        if gold_docs:
            # Add gold docs (they contain the answers)
            for doc in gold_docs:
                if doc.get('docid') not in self.doc_index:
                    all_docs.append(doc)

        self.documents = all_docs
        self.doc_index = {doc.get('docid', str(i)): doc for i, doc in enumerate(self.documents)}

    def execute(self, tool_name: str, arguments: dict) -> str:
        """Execute a search tool and return result."""
        if tool_name == "search":
            return self._search(arguments.get("query", ""), arguments.get("topk", 5))
        elif tool_name == "open_page":
            return self._open_page(arguments.get("docid", ""))
        else:
            return f"Unknown tool: {tool_name}. Use ctx_cli for context management."

    def _search(self, query: str, topk: int = 5) -> str:
        """
        Simple keyword search over documents.

        For production, this should use embeddings (like Qwen3-Embedding-8B).
        For fair comparison, we use keyword overlap scoring.
        """
        if not query:
            return "Error: Empty query"

        query_terms = set(query.lower().split())

        # Score documents by keyword overlap
        scored_docs = []
        for doc in self.documents:
            text = doc.get('text', '').lower()
            doc_terms = set(text.split())

            # Jaccard-like overlap score
            overlap = len(query_terms & doc_terms)
            if overlap > 0:
                score = overlap / len(query_terms)
                scored_docs.append((score, doc))

        # Sort by score and take top-k
        scored_docs.sort(key=lambda x: x[0], reverse=True)
        top_results = scored_docs[:topk]

        if not top_results:
            return "No results found for query."

        # Format results
        results = []
        for i, (score, doc) in enumerate(top_results, 1):
            snippet = doc.get('text', '')[:500] + "..." if len(doc.get('text', '')) > 500 else doc.get('text', '')
            results.append(
                f"[{i}] docid: {doc.get('docid', 'unknown')}\n"
                f"    url: {doc.get('url', 'N/A')}\n"
                f"    snippet: {snippet}"
            )

        return f"Found {len(top_results)} results:\n\n" + "\n\n".join(results)

    def _open_page(self, docid: str) -> str:
        """Retrieve full document content by ID."""
        if not docid:
            return "Error: No document ID provided"

        doc = self.doc_index.get(docid)
        if not doc:
            return f"Error: Document '{docid}' not found"

        return (
            f"Document: {docid}\n"
            f"URL: {doc.get('url', 'N/A')}\n"
            f"Content:\n{doc.get('text', 'No content available')}"
        )

def get_browsecomp_tools_with_ctx_cli():
    """
    Get combined tools: BrowseComp search + ECM ctx_cli.

    This allows the agent to:
    1. Search documents (search, open_page)
    2. Manage context via ctx_cli:
       - scope <name>: Create research workspace (like FoldAgent branch)
       - note -m "...": Save findings (like FoldAgent think)
       - return -m "ANSWER: ...": Complete with answer (like FoldAgent return)
       - status: Check current state
    """
    from ctx_cli import CTX_CLI_TOOL

    return BROWSECOMP_SEARCH_TOOLS + [CTX_CLI_TOOL]
