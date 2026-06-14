"""
Seeded in-memory tenant store.
Simulates SharePoint files with permission scopes.
Sits behind GraphAdapter so a real Microsoft Graph implementation can drop in.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Optional
import copy

# ── Seeded file corpus ────────────────────────────────────────────────────────

_INITIAL_FILES: List[Dict] = [
    {
        "id": "f1",
        "name": "2026_Executive_Salaries.xlsx",
        "type": "spreadsheet",
        "owner": "hr-admin@contoso.com",
        "scope": "everyone",   # over-shared — should be restricted
        "sensitivity": None,   # filled by Context agent
        "content": (
            "CONFIDENTIAL — Contoso Executive Compensation 2026\n"
            "VP of Sales: Rohan Mehta — Base ₹42,00,000 + Bonus ₹8,00,000 = Total ₹50,00,000\n"
            "VP of Engineering: Priya Nair — Base ₹45,00,000 + Bonus ₹9,00,000 = Total ₹54,00,000\n"
            "CFO: Amit Sharma — Base ₹80,00,000 + Bonus ₹20,00,000 = Total ₹1,00,00,000\n"
            "CEO: Sunita Rao — Base ₹1,20,00,000 + Bonus ₹40,00,000 = Total ₹1,60,00,000\n"
            "Source: HR Compensation Committee, March 2026. Do not distribute."
        ),
    },
    {
        "id": "f2",
        "name": "Project_Phoenix_MA_Term_Sheet.docx",
        "type": "document",
        "owner": "cfo@contoso.com",
        "scope": "everyone",
        "sensitivity": None,
        "content": (
            "STRICTLY CONFIDENTIAL — M&A Term Sheet\n"
            "Project Phoenix: Proposed acquisition of TechNova Pvt Ltd\n"
            "Valuation: ₹250 Crore (pre-money). Contoso offer: ₹310 Crore.\n"
            "Expected close: Q3 2026. Legal counsel: Khaitan & Co.\n"
            "Board approval pending. Material non-public information."
        ),
    },
    {
        "id": "f3",
        "name": "HR_PIP_Cases_Q1_2026.docx",
        "type": "document",
        "owner": "hr-admin@contoso.com",
        "scope": "everyone",
        "sensitivity": None,
        "content": (
            "CONFIDENTIAL HR — Performance Improvement Plans Q1 2026\n"
            "Employee: Vikram Singh (EMP-4421) — PIP initiated 2026-02-15. Manager: Deepa Joshi.\n"
            "Employee: Ananya Kumar (EMP-5530) — PIP initiated 2026-03-01. Manager: Ravi Pillai.\n"
            "Reason: Consistent underperformance on KPIs for 2 consecutive quarters.\n"
            "Restricted to HR and direct manager only."
        ),
    },
    {
        "id": "f4",
        "name": "Marketing_Campaign_Summer_2026.pptx",
        "type": "presentation",
        "owner": "marketing@contoso.com",
        "scope": "everyone",   # over-shared but NOT sensitive — decoy
        "sensitivity": None,
        "content": (
            "Contoso Summer Campaign 2026 — Brand Refresh\n"
            "Theme: 'Work Smarter with AI'. Target audience: SMB segment.\n"
            "Budget: ₹50 Lakh. Channels: LinkedIn, Google Ads, Partner webinars.\n"
            "Launch date: July 15, 2026. Contact: marketing@contoso.com"
        ),
    },
    {
        "id": "f5",
        "name": "Q1_2026_Earnings_Public_Draft.xlsx",
        "type": "spreadsheet",
        "owner": "finance@contoso.com",
        "scope": "restricted",  # properly restricted — safe
        "sensitivity": None,
        "content": (
            "Contoso Q1 2026 Earnings — Public Draft (pre-IR review)\n"
            "Revenue: ₹480 Crore (+18% YoY). EBITDA: ₹72 Crore.\n"
            "This is the public-facing draft pending IR sign-off."
        ),
    },
    {
        "id": "f6",
        "name": "Team_Offsite_Agenda_June_2026.docx",
        "type": "document",
        "owner": "ea@contoso.com",
        "scope": "restricted",  # properly restricted — safe
        "sensitivity": None,
        "content": (
            "Engineering Team Offsite — June 20-21, 2026\n"
            "Day 1: Product roadmap review, AI strategy session.\n"
            "Day 2: Hackathon (internal), team dinner at 7 PM.\n"
            "Venue: The Leela, Bengaluru. RSVP to ea@contoso.com"
        ),
    },
]

# ── GraphAdapter interface ────────────────────────────────────────────────────

class GraphAdapter(ABC):
    """
    Abstraction over Microsoft Graph file/permission access.
    SeededGraphAdapter uses in-memory data.
    RealGraphAdapter (post-hackathon) would call Graph API.
    """

    @abstractmethod
    def list_items(self) -> List[Dict]:
        """Return all items with id, name, type, owner, scope (not content)."""

    @abstractmethod
    def get_item_content(self, file_id: str) -> Optional[str]:
        """Return plaintext content of a file."""

    @abstractmethod
    def restrict_item(self, file_id: str) -> bool:
        """Change a file's scope from 'everyone' to 'restricted'. Returns success."""

    @abstractmethod
    def update_sensitivity(self, file_id: str, label: str) -> None:
        """Store the sensitivity label assigned by the Context agent."""

    @abstractmethod
    def reset(self) -> None:
        """Reset to initial state (for demo re-runs)."""


# ── Seeded implementation ─────────────────────────────────────────────────────

class SeededGraphAdapter(GraphAdapter):
    def __init__(self):
        self._store: List[Dict] = copy.deepcopy(_INITIAL_FILES)

    def list_items(self) -> List[Dict]:
        return [
            {k: v for k, v in f.items() if k != "content"}
            for f in self._store
        ]

    def get_item_content(self, file_id: str) -> Optional[str]:
        for f in self._store:
            if f["id"] == file_id:
                return f["content"]
        return None

    def restrict_item(self, file_id: str) -> bool:
        for f in self._store:
            if f["id"] == file_id:
                f["scope"] = "restricted"
                return True
        return False

    def update_sensitivity(self, file_id: str, label: str) -> None:
        for f in self._store:
            if f["id"] == file_id:
                f["sensitivity"] = label
                return

    def reset(self) -> None:
        self._store = copy.deepcopy(_INITIAL_FILES)


# ── Singleton for the app ─────────────────────────────────────────────────────

_adapter: Optional[SeededGraphAdapter] = None


def get_adapter() -> SeededGraphAdapter:
    global _adapter
    if _adapter is None:
        _adapter = SeededGraphAdapter()
    return _adapter
