"""Typed UI state: which tab, segment and sub-page each screen is on, plus unsaved editor drafts.

Kept in one place so a tab switch can close editors (no more coming back to a half-finished form) and the back
action (back arrow, Esc, Alt+←) knows what to close.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class UIState:
    foods_tab: str = "foods"            # foods | recipes | plans
    progress_tab: str = "garden"        # garden | trends
    trend_days: int = 30
    supp_edit: str | None = None        # supplement id, "new", or None
    supp_draft: Any = None
    recipe_edit: str | None = None      # recipe id, "new", or None
    recipe_draft: Any = None
    food_edit: str | None = None        # custom food id, "new", or None
    profile_page: str | None = None     # a Profile sub-page key, or None for the Profile menu
    supp_picker: bool = False           # Stack: the "add a supplement" picker
    onboarding: dict = field(default_factory=dict)  # wizard step + answers

    SUBPAGES = {"supps": ("supp_edit", "supp_picker"), "foods": ("recipe_edit", "food_edit"), "profile": ("profile_page",)}

    def sub_open(self, view: str) -> bool:
        return any(getattr(self, a) for a in self.SUBPAGES.get(view, ()))

    def close_sub(self, view: str) -> bool:
        """Close the open sub-page of `view`. Returns True if something was open."""
        was = self.sub_open(view)
        for a in self.SUBPAGES.get(view, ()):
            setattr(self, a, False if a == "supp_picker" else None)
        return was

    def key(self, view: str) -> str:
        """Identifies what's on screen, so a change of sub-page plays the entrance animation."""
        return "|".join(str(getattr(self, a)) for a in self.SUBPAGES.get(view, ())) + (
            f"|{self.progress_tab}" if view == "garden" else f"|{self.foods_tab}" if view == "foods" else "")
