"""Dynamic multi-agent orchestrator (Strands 'agents as tools').

An Orchestrator agent reasons about which specialist sub-agent to invoke and when, instead
of running a fixed pipeline. Each specialist is exposed to the orchestrator as a tool:

    retriever_agent  → RAG over the company's filings (Knowledge Base)
    analyst_agent    → reason over passages + market data into findings
    writer_agent     → compose the final cited brief

Each sub-agent runs its own autonomous tool-use loop. The orchestrator decides the order,
may re-invoke the retriever for more coverage, and stops when the brief is complete.
"""
from strands import Agent, tool
from strands.models import BedrockModel

from config import cfg
from progress import emit
from tools import market_data, retrieve_filings


def _model() -> BedrockModel:
    kwargs = dict(
        model_id=cfg.model_id,
        region_name=cfg.region,
        temperature=0.2,
        max_tokens=cfg.model_max_tokens,
    )
    # Attach the Bedrock Guardrail to every model call when configured.
    if cfg.guardrail_id:
        kwargs.update(
            guardrail_id=cfg.guardrail_id,
            guardrail_version=cfg.guardrail_version,
            guardrail_trace="enabled",
        )
    return BedrockModel(**kwargs)


# BedrockModel is a stateless client wrapper — build it once and share it across agents.
_MODEL = _model()

RETRIEVER_PROMPT = (
    "You are a filings researcher. Call retrieve_filings(query, company) — always pass the given "
    "company so results stay scoped to it. Return the numbered passages verbatim (keep their [n] "
    "markers and source URIs). Do not analyze — just gather and pass through."
)
ANALYST_PROMPT = (
    "You are a financial analyst. Using ONLY the passages you are given plus the market_data tool, "
    "produce structured findings: business summary, key financials, risks, outlook. Cite passages "
    "inline as [n] exactly as numbered. Never invent facts not in the passages or tool output."
)
WRITER_PROMPT = (
    "You are an equity research writer. Turn the findings into a concise brief (Summary, "
    "Financials, Risks, Outlook), preserving [n] citations and ending with a 'Sources' list "
    "mapping [n] → source URI. Omit any claim that lacks support."
)
ORCHESTRATOR_PROMPT = (
    "You orchestrate a financial-research workflow using three specialist sub-agents exposed to "
    "you as tools:\n"
    "  - retriever_agent(query, company): searches the company's filings; returns numbered passages\n"
    "  - analyst_agent(company, passages): analyzes passages + market data into findings\n"
    "  - writer_agent(company, findings): writes the final cited brief\n\n"
    "Decide which sub-agent to call and in what order — reason about it, don't assume a fixed "
    "path. The usual flow is retrieve → analyze → write, but if the analyst needs more coverage, "
    "call retriever_agent again with a different query before analyzing; never call a step before "
    "you have its inputs. Thread each sub-agent's output into the next call. When writer_agent "
    "returns a brief whose claims all carry [n] citations mapped to sources, return that brief "
    "verbatim as your final answer — keep the [n] markers and the Sources list intact."
)


class _Budget:
    """Caps how many sub-agent calls a single request may make (cost/loop guard)."""

    def __init__(self, limit: int):
        self.remaining = limit

    def spend(self, who: str) -> None:
        if self.remaining <= 0:
            raise RuntimeError(f"sub-agent call budget exhausted before calling {who}")
        self.remaining -= 1


def build_orchestrator() -> Agent:
    """Build a fresh orchestrator (call once per request → clean state + a fresh budget)."""
    budget = _Budget(cfg.max_subagent_calls)
    retrievals = {"n": 0}

    @tool
    def retriever_agent(query: str, company: str) -> str:
        """Search a company's filings and return numbered passages with source URIs.

        Call whenever you need grounding facts; may be called more than once with different
        queries if coverage is insufficient.
        """
        budget.spend("retriever_agent")
        retrievals["n"] += 1
        emit("🔎 I'll pull the relevant filings first."
             if retrievals["n"] == 1 else "🔎 Not enough yet — searching the filings again.")
        sub = Agent(model=_MODEL, tools=[retrieve_filings], system_prompt=RETRIEVER_PROMPT)
        return str(sub(f"Company: {company}\nRetrieve passages for: {query}"))

    @tool
    def analyst_agent(company: str, passages: str) -> str:
        """Analyze retrieved passages plus market data into structured findings with [n] cites."""
        budget.spend("analyst_agent")
        emit("📊 Good — I have the passages. Analyzing the financials now.")
        sub = Agent(model=_MODEL, tools=[market_data], system_prompt=ANALYST_PROMPT)
        return str(sub(f"Company: {company}\nPassages:\n{passages}"))

    @tool
    def writer_agent(company: str, findings: str) -> str:
        """Compose the final cited analyst brief from the analyst's findings."""
        budget.spend("writer_agent")
        emit("✍️ I have enough to go on — drafting the cited brief.")
        sub = Agent(model=_MODEL, system_prompt=WRITER_PROMPT)
        return str(sub(f"Company: {company}\nFindings:\n{findings}"))

    return Agent(
        model=_MODEL,
        tools=[retriever_agent, analyst_agent, writer_agent],
        system_prompt=ORCHESTRATOR_PROMPT,
    )
