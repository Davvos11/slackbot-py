import os
from datetime import datetime, timedelta, timezone

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
        if (datetime.now() - self.updated) > timedelta(minutes=1):
            self._update()

    def get_next(self, query: str, exclude: str | None = None) -> Event | None:
        now = datetime.now(timezone.utc)
        self._check_update()
        query = query.lower()
        for event in self.events:
            title = event.summary.lower()
            if event.start and event.start > now and query in title:
                if exclude is not None and exclude in title:
                    continue
                return event
        return None


def test():
    load_dotenv()
    calendar = Calendar()
    event = calendar.get_next("vckantie", "aanbetaling")
    if event is None:
        print("Geen volgende vckantie in de agenda gevonden")
        exit(0)
    delta = event.start - datetime.now(tz=event.start.tzinfo)
    hours, rem = divmod(delta.seconds, 3600)
    minutes, seconds = divmod(rem, 60)
    print(f"Nog {delta.days} dagen, {hours} uur en {minutes} minuten tot {event.summary.strip()}!")


if __name__ == '__main__':
    test()
