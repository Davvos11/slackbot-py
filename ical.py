import os
from datetime import datetime, timedelta

from dotenv import load_dotenv
from icalevents.icalevents import events
from icalevents.icalparser import Event


class Calendar:
    def __init__(self):
        load_dotenv()
        url = os.getenv("ICAL")
        start = datetime.now()
        end = start + timedelta(weeks=52)
        self.events = events(url=url, start=start, end=end, sort=True)

    def get_next(self, query: str) -> Event | None:
        query = query.lower()
        try:
            match = next(e for e in self.events if query in e.summary.lower())
        except StopIteration:
            return None
        return match
