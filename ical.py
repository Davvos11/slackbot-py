import os
from datetime import datetime, timedelta

from dotenv import load_dotenv
from icalevents.icalevents import events
from icalevents.icalparser import Event


class Calendar:
    events: list[Event]
    updated: datetime

    def __init__(self):
        self._update()

    def _update(self):
        load_dotenv()
        url = os.getenv("ICAL")
        start = datetime.now()
        end = start + timedelta(weeks=52)
        self.events = events(url=url, start=start, end=end, sort=True)
        self.updated = start

    def _check_update(self):
        if (datetime.now() - self.updated) < timedelta(seconds=10):
            self._update()

    def get_next(self, query: str) -> Event | None:
        self._check_update()
        query = query.lower()
        try:
            match = next(e for e in self.events if query in e.summary.lower())
        except StopIteration:
            return None
        return match
