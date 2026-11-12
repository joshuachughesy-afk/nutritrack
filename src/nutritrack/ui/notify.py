"""Notification delivery.

* Phones, macOS and Windows: the OS scheduler gets the full plan (core.reminders.plan_notifications) and delivers it
  even when the app is closed. Supplement reminders repeat daily and carry a "Mark taken" action.
* Browser / Linux desktop (no OS scheduling): an in-app loop checks every minute and shows what's due.
In-app, every due reminder also appears as a banner while the app is open.
"""
from __future__ import annotations

import asyncio
import hashlib
from datetime import date
from typing import TYPE_CHECKING


try:  # optional at import time so tests and plain web runs work without it
    import flet_notifications as ftn
except Exception:  # pragma: no cover
    ftn = None

if TYPE_CHECKING:
    from .app import App

SCHEDULING_PLATFORMS = {"android", "android_tv", "ios", "macos", "windows"}


class Notifier:
    def __init__(self, app: "App"):
        self.app = app
        self.service = None
        self._plan_hash: str | None = None
        self._sync_task: asyncio.Task | None = None
        if ftn is not None:
            try:
                self.service = ftn.Notifications(on_tap=self._on_tap, on_action=self._on_action)
            except Exception:
                self.service = None

    # ---------- capabilities ----------
    @property
    def can_schedule(self) -> bool:
        page = self.app.page
        plat = getattr(getattr(page, "platform", None), "value", "")
        return self.service is not None and not getattr(page, "web", False) and str(plat).lower() in SCHEDULING_PLATFORMS

    async def request_permission(self) -> bool:
        if self.service is None:
            return False
        try:
            return bool(await self.service.request_permissions())
        except Exception:
            return False

    # ---------- OS scheduling ----------
    def request_sync(self) -> None:
        """Debounced: rebuild the OS schedule shortly after the latest change."""
        if not self.can_schedule:
            return
        if self._sync_task and not self._sync_task.done():
            self._sync_task.cancel()
        self._sync_task = self.app.page.run_task(self._sync_later)

    async def _sync_later(self) -> None:
        await asyncio.sleep(1.5)
        await self.sync()

    async def sync(self) -> None:
        plan = self.app.svc.notification_plan()
        digest = hashlib.sha1(repr([(p.id, p.when.isoformat(), p.title, p.body) for p in plan]).encode()).hexdigest()
        if digest == self._plan_hash:
            return
        try:
            await self.service.cancel_all_pending()
            for p in plan:
                actions = [ftn.NotificationAction(id="taken", title="Mark taken")] if p.kind == "supplement" else None
                await self.service.schedule(
                    p.id, when=p.when, title=p.title, body=p.body, payload=p.payload, actions=actions,
                    match_components=ftn.DateTimeComponents.TIME if p.repeat_daily else None)
            self._plan_hash = digest
        except Exception as ex:  # never let reminders break the app
            self.app.toast(f"Couldn't schedule reminders: {ex}")

    # ---------- in-app loop ----------
    async def loop(self) -> None:
        """Once a minute: show due reminders, and refresh Today only when its pace check would actually change.

        Skipped entirely while the app is in the background (the OS scheduler covers reminders there), so an idle
        client costs the server nothing.
        """
        last_sig = None
        while True:
            await asyncio.sleep(60)
            if not self.app.visible:
                continue
            try:
                events = self.app.svc.due_now()
                for ev in events:
                    if not self.can_schedule and self.service is not None:
                        try:
                            await self.service.show(abs(hash(ev.key)) % 2**31, title=ev.title, body=ev.body, payload=ev.payload)
                        except Exception:
                            pass
                    self.app.banner(ev.title, ev.body, ev.payload)
                if self.app.view == "today":
                    sig = self.app.svc.pace_signature(self.app.date)
                    if events or sig != last_sig:
                        last_sig = sig
                        self.app.render()
            except Exception:
                pass

    async def test(self) -> None:
        shown = False
        if self.service is not None and await self.request_permission():
            try:
                await self.service.show(1, title="🌱 NutriTrack", body="Reminders are working. You'll get check-ins like this.")
                shown = True
            except Exception:
                shown = False
        if not shown:
            self.app.banner("🌱 Test reminder", "System notifications aren't available here, so reminders appear like this "
                            "inside the app.")

    # ---------- responses ----------
    def _on_tap(self, e) -> None:
        self.app.go("today", date.today().isoformat())

    def _on_action(self, e) -> None:
        payload = getattr(e, "payload", "") or ""
        if getattr(e, "action_id", "") == "taken" and payload.startswith("dose:"):
            self.mark_from_payload(payload)

    def mark_from_payload(self, payload: str) -> None:
        _, supp_id, time_str = payload.split(":", 2)
        supp = next((s for s in self.app.store.supplements() if s.id == supp_id), None)
        if supp:
            self.app.store.mark_dose(date.today().isoformat(), supp, time_str)
            self.app.toast(f"✓ {supp.name} marked as taken")
            self.app.render()
