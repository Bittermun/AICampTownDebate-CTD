"""
Research Tool: Web search capability for debaters.

Provides token-costed research ability using DuckDuckGo.
Costs are dynamic based on query length and content retrieved.
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SearchResult:
    """Result of a web search with dynamic cost calculation."""
    query: str
    snippets: list[str] = field(default_factory=list)
    titles: list[str] = field(default_factory=list)
    urls: list[str] = field(default_factory=list)
    error: Optional[str] = None
    
    @property
    def total_chars(self) -> int:
        """Total characters in all snippets."""
        return sum(len(s) for s in self.snippets)
    
    @property
    def token_cost(self) -> int:
        """Dynamic cost based on content processed.
        
        Query: 1 token per 20 chars
        Content: 1 token per 50 chars
        Minimum: 5 tokens per search
        """
        query_cost = max(1, len(self.query) // 20)
        content_cost = self.total_chars // 50
        return max(5, query_cost + content_cost)
    
    @property
    def summary(self) -> str:
        """Formatted summary for LLM context."""
        if self.error:
            return f"[RESEARCH_ERROR] {self.error}"
        if not self.snippets:
            return "[NO_RESULTS] No relevant information found."
        
        lines = [f"### Research Results for: {self.query}\n"]
        for i, (title, snippet) in enumerate(zip(self.titles, self.snippets), 1):
            lines.append(f"**{i}. {title}**")
            lines.append(f"{snippet}\n")
        return "\n".join(lines)


class ResearchTool:
    """Web search tool for debaters using DuckDuckGo.
    
    Usage:
        tool = ResearchTool()
        result = tool.search("AI regulation history")
        cost = result.token_cost  # Dynamic cost
        context = result.summary  # For LLM
    """
    
    def __init__(self, max_results: int = 3, region: str = "wt-wt"):
        """Initialize research tool.
        
        Args:
            max_results: Maximum search results to return
            region: DuckDuckGo region (wt-wt = worldwide)
        """
        self.max_results = max_results
        self.region = region
        self._ddgs = None
    
    def _get_client(self):
        """Lazy load DuckDuckGo client."""
        if self._ddgs is None:
            try:
                from ddgs import DDGS
                self._ddgs = DDGS()
            except ImportError:
                return None
        return self._ddgs
    
    def search(self, query: str) -> SearchResult:
        """Execute web search and return results with cost.
        
        Args:
            query: Search query string
            
        Returns:
            SearchResult with snippets, titles, urls, and token_cost
        """
        client = self._get_client()
        if client is None:
            return SearchResult(
                query=query,
                error="duckduckgo-search not installed. Run: pip install duckduckgo-search"
            )
        
        try:
            results = list(client.text(
                query,
                region=self.region,
                max_results=self.max_results,
            ))
            
            return SearchResult(
                query=query,
                snippets=[r.get("body", "") for r in results],
                titles=[r.get("title", "") for r in results],
                urls=[r.get("href", "") for r in results],
            )
        except Exception as e:
            return SearchResult(query=query, error=str(e))
    
    async def search_async(self, query: str) -> SearchResult:
        """Async version of search for parallel execution."""
        # DuckDuckGo is sync-only, wrap in executor
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.search, query)


# Singleton for shared use
_default_tool: Optional[ResearchTool] = None


def get_research_tool() -> ResearchTool:
    """Get or create the default research tool."""
    global _default_tool
    if _default_tool is None:
        _default_tool = ResearchTool()
    return _default_tool
