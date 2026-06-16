# CopilotGuard 🛡️

> **The security layer that stops Copilot from leaking what it was never supposed to see.**

Microsoft Build AI 2026 · Theme: **Security in the Agentic Future** + **Agent Swarms**

---

## 🚀 Live Demo

**👉 https://copilot-guard-production.up.railway.app/**

This is the official, live URL for the project — open it in any browser to use the CopilotGuard console (UI + API are served from this single link).

> **Note:** If the link doesn't load on your network, it's a local DNS issue with `*.up.railway.app` (some ISPs refuse it), **not** the app being down. Fix: switch your DNS to `1.1.1.1` / `8.8.8.8`, or open it on mobile data.

---

## The Problem

Enterprises deploying Microsoft 365 Copilot inherit a decade of accidental oversharing across SharePoint and OneDrive. A salary spreadsheet shared "Everyone" in 2019 was harmless when no one could find it. **Copilot finds it instantly — and answers questions about it to anyone who asks.**

```
Intern: "What does the VP of Sales earn?"
Copilot: "According to 2026_Executive_Salaries.xlsx, Rohan Mehta earns ₹50,00,000..."
```

This isn't a Copilot bug. It's Copilot doing exactly what it was designed to do — but on data that was never meant to be universally accessible. CopilotGuard fixes the exposure before the leak.

---

## Why Not Just Microsoft Purview?

Microsoft Purview / Restricted SharePoint Search detect oversharing at the **permissions layer**. CopilotGuard's unique angle is **agentic and Copilot-aware**:

| | Purview / SharePoint Admin | CopilotGuard |
|---|---|---|
| Detects over-shared files | ✅ | ✅ |
| Understands what Copilot would actually say | ❌ | ✅ |
| Generates the exact leaking prompt as proof | ❌ | ✅ |
| Reasons about *why* content is sensitive (AI) | ❌ | ✅ |
| Shows live before/after in Copilot | ❌ | ✅ |

CopilotGuard doesn't just flag permissions — it **proves the leak** and closes it.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  CopilotGuard Console                    │
│         (Single-page UI · Before/After Demo)             │
└───────────────┬─────────────────┬───────────────────────┘
                │                 │
        ┌───────▼──────┐  ┌───────▼──────────┐
        │ Copilot RAG  │  │   FastAPI Server  │
        │  Answerer    │  │   (SSE streaming) │
        └───────┬──────┘  └───────┬───────────┘
                │                 │
                │        ┌────────▼─────────────────┐
                │        │  AutoGen Swarm            │
                │        │  ┌──────────────────────┐ │
                │        │  │  1. Recon Agent      │ │
                │        │  │  2. Context Agent    │ │
                │        │  │  3. Attack Agent     │ │
                │        │  │  4. Remediation Agent│ │
                │        │  └──────────────────────┘ │
                │        └────────┬─────────────────┘
                │                 │
        ┌───────▼─────────────────▼──────┐
        │         GraphAdapter           │
        │  SeededGraphAdapter (demo)     │
        │  RealGraphAdapter  (prod ↓)    │
        └────────────────────────────────┘
                         │
              Microsoft Graph API
              (post-hackathon swap)
```

### Agent roles (AutoGen + Azure AI Foundry / GitHub Models)

| Agent | Role | Real AI call |
|---|---|---|
| **Recon** | Scans the tenant for files with `scope=everyone` | Summarises exposure risk |
| **Context** | Reads file content, classifies CRITICAL / WARNING / SAFE | LLM-powered sensitivity classification |
| **Attack** | Generates the exact Copilot query that would leak each CRITICAL file | Proves the leak is real |
| **Remediation** | Restricts the file scope + drafts a Teams alert to the owner | Generates professional alert |

### The mock→real swap (scalability story)

`GraphAdapter` is an abstract interface. The demo uses `SeededGraphAdapter` (6 seeded files in memory). Dropping in `RealGraphAdapter` requires:
1. An Entra app registration with `Sites.ReadWrite.All` + `Chat.ReadWrite` permissions
2. Implementing `list_items()`, `get_item_content()`, `restrict_item()` against the Graph API
3. Setting `GRAPH_TENANT_ID`, `GRAPH_CLIENT_ID`, `GRAPH_CLIENT_SECRET` in `.env`

The rest of the swarm, the UI, and the demo flow are unchanged.

---

## Setup

**Requirements:** Python 3.11+

### 1. Install dependencies

```bash
pip install -r backend/requirements.txt
```

### 2. Get a free GitHub Models token (2 minutes)

1. Go to **https://github.com/settings/tokens** → **Generate new token (classic)**
2. No scopes needed — just create it and copy the value
3. Create `.env` from the example:

```bash
cp .env.example .env
```

4. Open `.env` and replace `your_github_pat_here` with your token

### 3. Run the backend

```bash
uvicorn backend.main:app --reload --port 8000
```

### 4. Open the frontend

Open `frontend/index.html` in your browser, or visit **http://localhost:8000**

---

## Switching to Azure AI Foundry

Edit `.env`:

```env
MODEL_PROVIDER=azure
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_KEY=your-key
AZURE_OPENAI_DEPLOYMENT=gpt-4o
```

No code changes needed — `config.py` handles the swap.

---

## Demo Script (3 minutes)

> Run it live at **https://copilot-guard-production.up.railway.app/** (no local setup needed).

1. **Show the leak** — Ask Copilot *"What does the VP of Sales earn?"* → it answers with the real salary from the over-shared file.
2. **Run CopilotGuard** — Click "Run CopilotGuard". Watch the 4 agents reason live in the activity feed.
3. **Watch the proof** — The Attack agent prints the exact Copilot query that creates the leak.
4. **See the save** — After Remediation, ask the same question → Copilot now refuses. Risk score drops from 80 → 5.

---

## Evaluation Criteria Mapping

| Criterion (weight) | How CopilotGuard scores |
|---|---|
| **AI Integration & Intelligence Design (25%)** | 4 AutoGen agents making real GPT-4o calls; RAG answerer; Attack agent proves leak intelligently |
| **System Architecture & Engineering Quality (25%)** | GraphAdapter interface (mock→real), clean agent separation, SSE streaming, FastAPI |
| **Communication, Presentation & UX (15%)** | Live before/after console, real-time agent feed, risk score gauge |
| **Prototype Readiness & Scalability (15%)** | Works live; GraphAdapter boundary makes real-Graph swap a single-file change |
| **Problem Depth & Product Clarity (10%)** | Copilot weaponising existing oversharing — the #1 enterprise Copilot trust blocker |
| **Market Understanding & Product Fit (10%)** | Explicit Purview differentiation; positions as "Purview for the agentic era" |

---

## Microsoft AI Stack Used

- **AutoGen** — Multi-agent orchestration (Recon → Context → Attack → Remediation)
- **Azure AI Foundry / GitHub Models** — GPT-4o for all agent reasoning and RAG
- **Semantic Kernel** — (architecture-compatible; swap AutoGen for SK with no other changes)

---

## Team

Submitted to Microsoft Build AI 2026 — Security in the Agentic Future track.
