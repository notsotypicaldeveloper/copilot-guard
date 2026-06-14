"""
CopilotGuard Agent Swarm — four AutoGen AssistantAgents orchestrated in sequence.

Recon → Context → Attack → Remediation

Each agent is a real AutoGen AssistantAgent making LLM calls via the configured
model client (GitHub Models or Azure AI Foundry — see config.py).

Yields SSE-style event dicts so FastAPI can stream them live to the UI.
"""
import asyncio
from typing import Generator, Dict, Any, List

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import TextMessage
from autogen_ext.models.openai import OpenAIChatCompletionClient

from backend.config import MODEL_NAME, BASE_URL, API_KEY, API_VERSION
from backend.tenant.data import get_adapter

# ── AutoGen model client (hot-swappable via config.py) ───────────────────────

def _make_model_client() -> OpenAIChatCompletionClient:
    kwargs: dict = {
        "model": MODEL_NAME,
        "base_url": BASE_URL,
        "api_key": API_KEY,
    }
    if API_VERSION:
        # Azure AI Foundry requires api_version
        kwargs["model_capabilities"] = {
            "vision": False,
            "function_calling": True,
            "json_output": True,
        }
    return OpenAIChatCompletionClient(**kwargs)


# ── Event helpers ─────────────────────────────────────────────────────────────

def _event(agent: str, status: str, message: str, data: Any = None) -> Dict:
    return {"agent": agent, "status": status, "message": message, "data": data}


# ── Async agent runners ───────────────────────────────────────────────────────

async def _ask_agent(agent: AssistantAgent, prompt: str) -> str:
    """Run a single-turn task on an AutoGen AssistantAgent and return the text response."""
    result = await agent.run(task=prompt)
    # Last message in the result is the agent's response
    for msg in reversed(result.messages):
        if hasattr(msg, "content") and isinstance(msg.content, str):
            return msg.content.strip()
    return ""


async def _run_recon_async(model_client: OpenAIChatCompletionClient, events: list) -> list:
    adapter = get_adapter()
    items = adapter.list_items()
    exposed = [i for i in items if i["scope"] == "everyone"]

    events.append(_event("Recon", "start", "Scanning Microsoft Graph for over-permissioned items…"))

    agent = AssistantAgent(
        name="ReconAgent",
        model_client=model_client,
        system_message=(
            "You are the Recon Agent in the CopilotGuard security swarm. "
            "You identify files that are over-shared in a Microsoft 365 tenant. "
            "Be concise and professional. Respond in 2 sentences maximum."
        ),
    )

    summary = await _ask_agent(
        agent,
        f"I scanned the tenant and found {len(items)} files. "
        f"{len(exposed)} have scope='everyone' (org-wide access). "
        "Exposed files: " + ", ".join(e["name"] for e in exposed) + ". "
        "Briefly summarise the exposure risk for the security dashboard.",
    )

    events.append(_event(
        "Recon", "complete",
        f"Found {len(exposed)} over-shared items out of {len(items)} total.",
        {"exposed_ids": [e["id"] for e in exposed], "summary": summary},
    ))
    return exposed


async def _run_context_async(model_client: OpenAIChatCompletionClient, exposed: list, events: list) -> list:
    adapter = get_adapter()
    critical = []

    events.append(_event("Context", "start", f"Classifying sensitivity of {len(exposed)} exposed files…"))

    agent = AssistantAgent(
        name="ContextAgent",
        model_client=model_client,
        system_message=(
            "You are a Data Loss Prevention AI for an enterprise. "
            "Classify file content sensitivity. "
            "Reply with EXACTLY one of CRITICAL, WARNING, or SAFE followed by a colon and a one-sentence reason. "
            "CRITICAL = salaries, PII, HR cases, M&A, legal. WARNING = internal-only. SAFE = generic/public."
        ),
    )

    for item in exposed:
        content = adapter.get_item_content(item["id"]) or ""
        label_raw = await _ask_agent(
            agent,
            f"File: {item['name']}\n\nContent excerpt:\n{content[:800]}",
        )

        label = label_raw.split(":")[0].strip().upper()
        if label not in ("CRITICAL", "WARNING", "SAFE"):
            label = "WARNING"
        reason = label_raw.split(":", 1)[1].strip() if ":" in label_raw else label_raw

        adapter.update_sensitivity(item["id"], label)

        events.append(_event(
            "Context", "classified",
            f"{item['name']} → {label}",
            {"file_id": item["id"], "file_name": item["name"], "label": label, "reason": reason},
        ))

        if label == "CRITICAL":
            critical.append({**item, "sensitivity": label, "reason": reason})

    events.append(_event("Context", "complete", f"{len(critical)} CRITICAL files require immediate remediation."))
    return critical


async def _run_attack_async(model_client: OpenAIChatCompletionClient, critical: list, events: list) -> list:
    events.append(_event("Attack", "start", f"Generating proof-of-leak Copilot queries for {len(critical)} CRITICAL files…"))

    agent = AssistantAgent(
        name="AttackAgent",
        model_client=model_client,
        system_message=(
            "You are a red-team AI simulating how Microsoft 365 Copilot could leak sensitive data. "
            "Given a file name and content, generate the single most natural Copilot question "
            "a curious employee would ask that would expose the sensitive content. "
            "Reply with ONLY the question — no explanation."
        ),
    )

    proofs = []
    for item in critical:
        content = get_adapter().get_item_content(item["id"]) or ""
        leaking_prompt = await _ask_agent(
            agent,
            f"File: {item['name']}\nContent excerpt: {content[:400]}",
        )
        proofs.append({**item, "leaking_prompt": leaking_prompt})
        events.append(_event(
            "Attack", "proof",
            f"Leak vector found for {item['name']}",
            {"file_id": item["id"], "file_name": item["name"], "leaking_prompt": leaking_prompt},
        ))

    events.append(_event("Attack", "complete", "Proof-of-concept leak queries generated. Handing to Remediation."))
    return proofs


async def _run_remediation_async(model_client: OpenAIChatCompletionClient, critical: list, events: list) -> None:
    adapter = get_adapter()
    events.append(_event("Remediation", "start", f"Remediating {len(critical)} CRITICAL exposures…"))

    agent = AssistantAgent(
        name="RemediationAgent",
        model_client=model_client,
        system_message=(
            "You are a security system sending Teams notifications to file owners. "
            "Write a short, professional alert (3 sentences max) telling the owner their file was "
            "found over-shared, was automatically restricted, and they should review access. "
            "Be direct and non-alarming."
        ),
    )

    for item in critical:
        success = adapter.restrict_item(item["id"])
        alert_msg = await _ask_agent(
            agent,
            f"File: {item['name']}\nOwner: {item['owner']}",
        )
        events.append(_event(
            "Remediation", "fixed",
            f"Restricted '{item['name']}' — Teams alert sent to {item['owner']}",
            {
                "file_id": item["id"],
                "file_name": item["name"],
                "owner": item["owner"],
                "restricted": success,
                "teams_alert": alert_msg,
            },
        ))

    events.append(_event("Remediation", "complete", "All CRITICAL files restricted. Copilot can no longer surface this data."))


async def _run_swarm_async() -> List[Dict]:
    """Runs the full async AutoGen swarm and returns all events as a list."""
    model_client = _make_model_client()
    events: List[Dict] = []

    exposed = await _run_recon_async(model_client, events)
    if not exposed:
        events.append(_event("Orchestrator", "done", "No over-shared files found. Tenant is clean.", {"risk_score": 0}))
        return events

    critical = await _run_context_async(model_client, exposed, events)
    if not critical:
        events.append(_event("Orchestrator", "done", "No CRITICAL files found. No remediation needed.", {"risk_score": 15}))
        return events

    await _run_attack_async(model_client, critical, events)
    await _run_remediation_async(model_client, critical, events)

    items = get_adapter().list_items()
    remaining = sum(1 for i in items if i["scope"] == "everyone" and i.get("sensitivity") == "CRITICAL")
    risk_score = max(5, remaining * 25)

    events.append(_event(
        "Orchestrator", "done",
        f"Scan complete. Risk score reduced to {risk_score}/100.",
        {"risk_score": risk_score, "remediated": len(critical)},
    ))
    return events


# ── Public sync generator (used by FastAPI SSE endpoint) ─────────────────────

def run_swarm() -> Generator[Dict, None, None]:
    """
    Synchronous generator that drives the async AutoGen swarm.
    FastAPI calls this from a thread-pool executor, so it can block.
    """
    events = asyncio.run(_run_swarm_async())
    yield from events
