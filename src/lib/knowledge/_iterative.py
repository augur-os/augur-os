"""Iterative LLM-in-the-loop search and circuit breaker for memory search.

ADR-033 hardening: iterative search via AI bridge, exponential backoff retry,
circuit breaker for sustained API outages.
"""

import json
import re
import time
from typing import Any, Optional

from src.logging import get_entity_logger

from ._types import SearchEvaluation, SearchMode, SearchResult, _normalize_path

logger = get_entity_logger(__name__)


class IterativeMixin:
    """Mixin providing iterative LLM search and circuit breaker for MemorySearcher.

    Expects the host class to have:
      - self._config: dict
      - self._search_root: Path
      - self._ripgrep_search() method
      - self._infer_category() method
      - self._extract_date() method
      - self._calculate_relevance() method
      - self.search() method
    """

    # Circuit breaker: number of consecutive LLM failures before opening the circuit
    _CIRCUIT_BREAKER_THRESHOLD = 3
    # Circuit breaker: seconds to wait before allowing LLM calls again
    _CIRCUIT_BREAKER_COOLDOWN = 300  # 5 minutes

    # Class-level circuit breaker state (shared across instances in the same process)
    _cb_failure_count: int = 0
    _cb_open_since: Optional[float] = None

    def _get_llm_client(self) -> Any:
        """Create an LLM client via the AI bridge, respecting user's llm.yaml config.

        Returns:
            An LLMClient instance, or None if AI bridge is unavailable.
        """
        try:
            import importlib.util as _ilu
            from src.config.paths import get_project_root, get_project_brain_skills_dir

            _ai_lib = get_project_brain_skills_dir(get_project_root()) / "ai" / "augur" / "lib" / "__init__.py"
            _ai_spec = _ilu.spec_from_file_location("ai_lib", _ai_lib)
            _ai_mod = _ilu.module_from_spec(_ai_spec)
            _ai_spec.loader.exec_module(_ai_mod)
            load_llm_config = _ai_mod.load_llm_config
            resolve_llm_profile = _ai_mod.resolve_llm_profile
            create_llm_client = _ai_mod.create_llm_client

            config = load_llm_config()
            profile = resolve_llm_profile(
                config,
                task="iterative_search",
                context="services/knowledge",
            )
            return create_llm_client(profile)
        except Exception as e:
            logger.info(f"AI bridge unavailable for iterative search: {e}")
            return None

    def _iterative_search(
        self,
        query: str,
        max_rounds: Optional[int] = None,
        top_k: int = 5,
    ) -> list[SearchResult]:
        """Claude Code-style iterative search:
        1. Grep with initial query
        2. Ask LLM (via AI bridge) if results are sufficient
        3. If not, LLM suggests refined query
        4. Repeat up to max_rounds
        5. Fall back to static scoring if AI bridge unavailable
        """
        # Read config
        iter_config = self._config.get("advanced", {}).get("iterative_search", {})
        if not iter_config.get("enabled", False):
            if iter_config.get("fallback_to_static", True):
                logger.info("Iterative search disabled in config, falling back to HYBRID")
                return self.search(query, mode=SearchMode.HYBRID, top_k=top_k)
            return []

        if max_rounds is None:
            max_rounds = iter_config.get("max_rounds", 3)

        client = self._get_llm_client()
        if client is None:
            logger.info("AI bridge unavailable, falling back to HYBRID mode")
            return self.search(query, mode=SearchMode.HYBRID, top_k=top_k)

        all_results: list[SearchResult] = []
        current_query = query
        llm_client_failed = False

        for round_num in range(max_rounds):
            # Step 1: Ripgrep search
            rg_results = self._ripgrep_search(current_query, self._search_root)
            round_results = self._convert_rg_to_search_results(rg_results, query=query)
            all_results.extend(round_results)

            # Step 2: Ask LLM if we have enough context
            try:
                evaluation = self._evaluate_results(client, query, round_results)
            except Exception as e:
                if self._is_expected_auth_error(e):
                    logger.info(f"LLM evaluation skipped in round {round_num + 1} (no valid API key)")
                elif self._is_non_retryable_error(e):
                    logger.warning(
                        f"LLM evaluation skipped in round {round_num + 1} (permanent API error — "
                        f"{type(e).__name__}). Error: {e}"
                    )
                else:
                    logger.warning(
                        f"LLM evaluation failed in round {round_num + 1} (transient, retries exhausted — "
                        f"{type(e).__name__}). Error: {e}"
                    )
                llm_client_failed = True
                break

            if evaluation.sufficient:
                break

            # Step 3: Refine query based on LLM feedback
            refined = evaluation.refined_query or query
            if len(refined) > 200:
                refined = refined[:200]
            current_query = refined

        # Deduplicate accumulated results
        seen: dict[tuple, SearchResult] = {}
        for r in all_results:
            key = (_normalize_path(r.file_path), r.line_number)
            existing = seen.get(key)
            if existing is None or r.relevance > existing.relevance:
                seen[key] = r
        deduped = list(seen.values())

        # Step 4: LLM ranks final results -- skip if client already failed
        if llm_client_failed:
            logger.info("Skipping LLM ranking (client unavailable), using static relevance")
            deduped.sort(key=lambda x: x.relevance, reverse=True)
            return deduped[:top_k]

        try:
            return self._rank_results(client, query, deduped, top_k)
        except Exception as e:
            if self._is_expected_auth_error(e):
                logger.info("LLM ranking skipped (no valid API key), using static relevance")
            elif self._is_non_retryable_error(e):
                logger.warning(
                    f"LLM ranking skipped (permanent API error — {type(e).__name__}), "
                    f"using static relevance. Error: {e}"
                )
            else:
                logger.warning(
                    f"LLM ranking failed (transient, retries exhausted — {type(e).__name__}), "
                    f"using static relevance. Error: {e}"
                )
            deduped.sort(key=lambda x: x.relevance, reverse=True)
            return deduped[:top_k]

    def _convert_rg_to_search_results(self, rg_results: list[dict], query: str = "") -> list[SearchResult]:
        """Convert raw ripgrep match dicts to SearchResult objects."""
        results = []
        for match in rg_results:
            match_source = "daily" if "/daily/" in match["path"] else "curated"
            results.append(
                SearchResult(
                    content=match["content"],
                    source=match_source,
                    category=self._infer_category(match["content"]),
                    date=self._extract_date(match["path"], match["content"]),
                    relevance=self._calculate_relevance(query, match["content"]),
                    file_path=match["path"],
                    line_number=match["line_number"],
                )
            )
        return results

    # ------------------------------------------------------------------
    # Error classification
    # ------------------------------------------------------------------

    @staticmethod
    def _is_expected_auth_error(e: Exception) -> bool:
        """Return True if the error is an expected auth/key misconfiguration."""
        err_str = str(e).lower()
        return any(
            kw in err_str
            for kw in (
                "authentication",
                "invalid_api_key",
                "api key",
                "api_key",
                "unauthorized",
            )
        )

    @staticmethod
    def _is_non_retryable_error(e: Exception) -> bool:
        """Return True if the error should not be retried."""
        err_str = str(e).lower()
        if any(
            kw in err_str
            for kw in (
                "authentication",
                "unauthorized",
                "forbidden",
                "invalid_api_key",
                "quota",
                "api key",
                "api_key",
                "missing model",
                "empty command",
            )
        ):
            return True
        code_match = re.search(r"llm request failed \((\d{3})\)", err_str)
        if code_match:
            code = int(code_match.group(1))
            if 400 <= code < 500 and code != 429:
                return True
        return False

    # ------------------------------------------------------------------
    # Circuit breaker
    # ------------------------------------------------------------------

    @classmethod
    def _circuit_breaker_is_open(cls) -> bool:
        """Return True if the circuit breaker is open (LLM calls should be skipped)."""
        if cls._cb_open_since is None:
            return False
        elapsed = time.monotonic() - cls._cb_open_since
        if elapsed >= cls._CIRCUIT_BREAKER_COOLDOWN:
            cls._cb_failure_count = 0
            cls._cb_open_since = None
            logger.info("LLM circuit breaker reset after cooldown; allowing probe call")
            return False
        return True

    @classmethod
    def _circuit_breaker_record_failure(cls) -> None:
        """Record an LLM failure; open the circuit if threshold is reached."""
        cls._cb_failure_count += 1
        if cls._cb_failure_count >= cls._CIRCUIT_BREAKER_THRESHOLD and cls._cb_open_since is None:
            cls._cb_open_since = time.monotonic()
            logger.warning(
                f"LLM circuit breaker OPEN after {cls._cb_failure_count} consecutive failures; "
                f"skipping LLM calls for {cls._CIRCUIT_BREAKER_COOLDOWN}s"
            )

    @classmethod
    def _circuit_breaker_record_success(cls) -> None:
        """Reset the circuit breaker on a successful LLM call."""
        if cls._cb_failure_count > 0 or cls._cb_open_since is not None:
            logger.info("LLM circuit breaker reset after successful call")
        cls._cb_failure_count = 0
        cls._cb_open_since = None

    # ------------------------------------------------------------------
    # LLM retry and evaluation
    # ------------------------------------------------------------------

    def _call_llm_with_retry(self, client: Any, system: str, prompt: str, max_retries: int = 5) -> dict:
        """Call client.generate_json with exponential backoff retry."""
        if max_retries <= 0:
            raise RuntimeError("_call_llm_with_retry called with max_retries=0; cannot make any attempts")
        if self._circuit_breaker_is_open():
            raise RuntimeError(
                f"LLM circuit breaker is open (too many recent API failures); skipping call for {self._CIRCUIT_BREAKER_COOLDOWN}s"
            )
        client_type = type(client).__name__
        last_exc: Optional[Exception] = None
        for attempt in range(max_retries):
            try:
                result = client.generate_json(
                    system=system,
                    prompt=prompt,
                    temperature=0.1,
                    max_tokens=200,
                )
                self._circuit_breaker_record_success()
                return result
            except Exception as e:
                last_exc = e
                if self._is_non_retryable_error(e):
                    if self._is_expected_auth_error(e):
                        logger.info(f"LLM unavailable [{client_type}] (no valid API key): {e}")
                    else:
                        logger.warning(
                            f"Non-retryable API error [{client_type}] ({type(e).__name__}, attempt {attempt + 1}): {e}"
                        )
                    self._circuit_breaker_record_failure()
                    raise
                if attempt < max_retries - 1:
                    backoff = min(2 ** (attempt + 1), 30)
                    logger.warning(
                        f"Transient API error [{client_type}] ({type(e).__name__}, attempt {attempt + 1}/{max_retries}), "
                        f"retrying in {backoff}s: {e}"
                    )
                    time.sleep(backoff)
                else:
                    logger.warning(f"API error [{client_type}] ({type(e).__name__}) after {max_retries} attempts: {e}")
        self._circuit_breaker_record_failure()
        if last_exc is not None:
            raise last_exc
        raise RuntimeError(f"_call_llm_with_retry called with max_retries={max_retries}")

    def _evaluate_results(self, client: Any, original_query: str, results: list[SearchResult]) -> SearchEvaluation:
        """Ask the LLM whether current results answer the query."""
        if not results:
            return SearchEvaluation(
                sufficient=False,
                refined_query=original_query,
                reasoning="No results found",
            )

        results_text = "\n".join(f"- {r.content}" for r in results[:20])

        response = self._call_llm_with_retry(
            client,
            system="You evaluate search results for relevance. Return JSON.",
            prompt=(
                f"Original query: {original_query}\n\n"
                f"Search results:\n{results_text}\n\n"
                "Do these results sufficiently answer the query? "
                'Return JSON: {"sufficient": bool, "refined_query": "...", "reasoning": "..."}\n'
                "If not sufficient, refined_query should be a better ripgrep regex pattern."
            ),
        )

        return SearchEvaluation(
            sufficient=response.get("sufficient", True),
            refined_query=response.get("refined_query", original_query),
            reasoning=response.get("reasoning", ""),
        )

    def _rank_results(self, client: Any, query: str, results: list[SearchResult], top_k: int) -> list[SearchResult]:
        """Ask the LLM to rank results by relevance."""
        if not results:
            return []
        top_k = max(1, top_k)

        indexed = [{"idx": i, "content": r.content[:200]} for i, r in enumerate(results[:30])]

        response = self._call_llm_with_retry(
            client,
            system="You rank search results by relevance. Return JSON.",
            prompt=(
                f"Query: {query}\n\n"
                f"Results: {json.dumps(indexed)}\n\n"
                f'{{"ranked_indices": [idx, idx, ...]}} '
                f"ordered by relevance (most relevant first). Include at most {top_k} indices."
            ),
        )

        ranked_indices = response.get("ranked_indices", list(range(min(top_k, len(results)))))
        ranked = []
        for i, idx in enumerate(ranked_indices[:top_k]):
            if isinstance(idx, int) and 0 <= idx < len(results):
                r = results[idx]
                ranked.append(
                    SearchResult(
                        content=r.content,
                        source=r.source,
                        category=r.category,
                        date=r.date,
                        relevance=1.0 - (i / top_k),
                        file_path=r.file_path,
                        line_number=r.line_number,
                        context=r.context,
                        scope=r.scope,
                    )
                )
        return ranked
