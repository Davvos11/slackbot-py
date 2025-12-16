import os
import random
import re
from datetime import datetime

from ical import Calendar

from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

load_dotenv()
app = App(token=os.environ.get("SLACK_BOT_TOKEN"))
calendar = Calendar()

emoji = [
    ":partyparrot:",
    ":vo::sgoeed:",
    ":partyblob:",
    ":partyvibe:",
    ":jayeshoppa:",
    ":borrele:",
]


@app.message(re.compile(r"is het al vckantie", re.IGNORECASE))
def message_hello(message, say):
    event = calendar.get_next("vckantie")
    if event is None:
        say(text="Geen volgende vckantie in de agenda gevonden :sad_sunglasses:")
        return
    delta = event.start - datetime.now(tz=event.start.tzinfo)
    hours, rem = divmod(delta.seconds, 3600)
    minutes, seconds = divmod(rem, 60)
    say(text=f"Nog {delta.days} dagen, {hours} uur en {minutes} minuten tot {event.summary}! {random.choice(emoji)}")


if __name__ == "__main__":
    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()
