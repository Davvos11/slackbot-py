import os
import re
from dataclasses import dataclass
from datetime import datetime
from time import sleep
from typing import Optional, Any
from urllib.parse import urlencode

import requests
import schedule
from dotenv import load_dotenv
from requests import HTTPError

from slack import send_trein_message, send_error_message


class NS:
    def __init__(self):
        self.API_KEY = os.getenv("NS_API_KEY", "")
        self.stations = self.get_stations()

    def _get(self, url: str, params: Optional[dict] = None):
        res = requests.get(url, headers={'Cache-Control': 'no-cache', 'Ocp-Apim-Subscription-Key': self.API_KEY},
                           params=params)
        res.raise_for_status()
        return res

    def _get_json(self, url: str, params: Optional[dict] = None):
        return self._get(url, params).json()

    def _get_text(self, url: str, params: Optional[dict] = None):
        return self._get(url, params).text

    def get_trip(self, time: str, from_station: str, to_station: str, via_station: Optional[str] = None) -> list[
        'Trip']:
        today = datetime.today()
        timestamp = today.strftime('%Y-%m-%dT') + time + ":00"

        params = {"fromStation": from_station, "toStation": to_station, "dateTime": timestamp}
        if via_station:
            params["viaStation"] = via_station

        response = self._get_json("https://gateway.apiportal.ns.nl/reisinformatie-api/api/v3/trips", params=params)
        return Trip.from_data(response)

    def get_train(self, trein_nr: int, station: str) -> 'Train':
        response = self._get_json(
            f"https://gateway.apiportal.ns.nl/virtual-train-api/v1/trein?ids={trein_nr}&stations={station}")
        result = Train.from_data(response)
        return result

    def get_stations(self) -> dict[str, str]:
        response = self._get_json("https://gateway.apiportal.ns.nl/nsapp-stations/v3?includeNonPlannableStations=false")
        stations = [(station["id"]["code"], station["names"]["long"]) for station in response["payload"]]
        return dict(stations)

    def generate_reisplanner_url(self, time: str, from_station: str, to_station: str,
                                 via_station: Optional[str] = None) -> str:
        query = {
            "vertrek": self.stations.get(from_station),
            "vertrektype": "treinstation",
            "aankomst": self.stations.get(to_station),
            "aankomsttype": "treinstation",
            "type": "vertrek",
            "tijd": time,
            "firstMileModality": "PUBLIC_TRANSPORT",
            "lastMileModality": "PUBLIC_TRANSPORT",
        }
        if via_station:
            query["via"] = self.stations.get(via_station)
            query["viatype"] = "treinstation"

        return f"https://www.ns.nl/reisplanner/#/?{urlencode(query)}"


@dataclass
class Trip:
    duration_planned: int
    duration_actual: int
    transfers: int
    message: Optional[str]
    legs: list['Leg']
    status: str
    url: Optional[str]
    crowd_forecast: str

    def get_drukte_emoji(self):
        match self.crowd_forecast:
            case "LOW":
                return ":rustig:"
            case "MEDIUM":
                return ":gemiddeld_druk:"
            case "HIGH":
                return ":druk:"
            case _:
                return ""

    @property
    def cancelled(self):
        return any(l.cancelled for l in self.legs)

    @staticmethod
    def from_data(data: dict) -> list['Trip']:
        result = []
        trips = data['trips']
        for trip in trips:
            duration_planned = trip['plannedDurationInMinutes']
            duration_actual = trip['actualDurationInMinutes']
            transfers = trip['transfers']
            message = trip.get('primaryMessage')
            if message:
                title = message.get('title')
                content = message.get('message', {}).get('text')
                if content:
                    message = f"{title}  \n{content}"
                else:
                    message = title
            status = trip.get('status')
            trip_forecast = trip.get('crowdForecast')
            url = trip.get('shareUrl', {}).get('uri')
            legs = []
            legs_data = trip['legs']
            for leg in legs_data:
                if leg.get('travelType') != "PUBLIC_TRANSIT":
                    continue
                name = leg.get('name')
                nr_match = re.search(r'\S+ (\d+)', name)
                ritnummer = int(nr_match.group(1)) if nr_match else 0
                notes = leg.get('product', {}).get('notes', [])
                description = get_desc_from_notes(notes, ['PRODUCT_INTERMEDIATE_STOPS'])
                origin = leg['origin']
                track_planned = origin.get('plannedTrack')
                track_actual = origin.get('actualTrack')
                datetime_planned = origin.get('plannedDateTime')
                if datetime_planned:
                    datetime_planned = datetime.strptime(datetime_planned, '%Y-%m-%dT%H:%M:%S%z')
                datetime_actual = origin.get('actualDateTime')
                if datetime_actual:
                    datetime_actual = datetime.strptime(datetime_actual, '%Y-%m-%dT%H:%M:%S%z')
                cancelled = leg['cancelled']
                from_station = leg.get('origin', dict()).get('stationCode')
                leg_forecast = leg.get('crowdForecast')
                legs.append(Leg(ritnummer, from_station, description, track_planned, track_actual, datetime_planned,
                                datetime_actual, cancelled, leg_forecast))
            result.append(Trip(duration_planned, duration_actual, transfers, message, legs, status, url, trip_forecast))
        return result


@dataclass
class TrainPart:
    materieelnummer: int
    type: str
    bakken: list


@dataclass
class Train:
    ritnummer: int
    station: str
    type: str
    lengte: int
    materieeldelen: list[TrainPart]

    def get_treinposities(self, dt: datetime) -> str:
        date_str = dt.strftime('%Y%m%d')
        return f"https://treinposities.nl/ritinfo/{date_str}/{self.ritnummer}"

    @staticmethod
    def from_data(data: list[dict]) -> 'Train':
        data = data[0]
        delen = [
            TrainPart(
                materieelnummer=part_data['materieelnummer'],
                type=part_data['type'],
                bakken=part_data['bakken'],
            )
            for part_data in data['materieeldelen']
        ]

        return Train(
            ritnummer=data['ritnummer'],
            station=data['station'],
            type=data['type'],
            lengte=data['lengte'],
            materieeldelen=delen,
        )


def get_desc_from_notes(notes: list[list[dict[str, Any]]], ignore: list[str]) -> str:
    output = ""
    for row in notes:
        for note in row:
            if note['key'] not in ignore:
                output += note['value'] + " "
    return output.strip()


@dataclass
class Leg:
    ritnummer: int
    from_station: str
    description: str
    track_planned: Optional[int]
    track_actual: Optional[int]
    datetime_planned: Optional[datetime]
    datetime_actual: Optional[datetime]
    cancelled: bool
    crowd_forecast: str

    def get_drukte_emoji(self):
        match self.crowd_forecast:
            case "LOW":
                return ":rustig:"
            case "MEDIUM":
                return ":gemiddeld_druk:"
            case "HIGH":
                return ":druk:"
            case _:
                return ""


def send_message(time: str, journeys: int, user_id: str, from_station: str, to_station: str,
                 via_station: Optional[str]):
    print(f"Sending message: {user_id} {time} {from_station} -> {via_station} -> {to_station} (max {journeys})")
    ns = NS()
    try:
        trips = ns.get_trip(time, from_station, to_station, via_station)
        trains = dict()
        for trip in trips:
            for leg in trip.legs:
                trains[leg.ritnummer] = ns.get_train(leg.ritnummer, leg.from_station)
        url = ns.generate_reisplanner_url(time, from_station, to_station, via_station)
        send_trein_message(trips, trains, journeys, url, user_id)
    except HTTPError as e:
        if data := e.response.text:
            send_error_message(data)
        else:
            send_error_message(str(e))
    except Exception as e:
        send_error_message(str(e))


def main():
    load_dotenv()
    # send_message("18:56", journeys=3, user_id="UP1H87YA3", from_station="DT", to_station="UT", via_station="RTD")
    # exit()

    # Note: de afkortingen van stations kan je vinden op https://zonindetrein.nl/api/stations

    # David:
    schedule.every().monday.at("07:00").do(send_message, time="07:51", journeys=1, user_id="UP1H87YA3",
                                           from_station="UT", to_station="PT", via_station=None)
    schedule.every().monday.at("16:00").do(send_message, time="16:29", journeys=1, user_id="UP1H87YA3",
                                           from_station="PT", to_station="UT", via_station=None)
    schedule.every().tuesday.at("07:00").do(send_message, time="07:51", journeys=1, user_id="UP1H87YA3",
                                            from_station="UT", to_station="PT", via_station=None)
    schedule.every().tuesday.at("16:00").do(send_message, time="16:29", journeys=1, user_id="UP1H87YA3",
                                            from_station="PT", to_station="UT", via_station=None)
    schedule.every().thursday.at("07:00").do(send_message, time="07:51", journeys=1, user_id="UP1H87YA3",
                                             from_station="UT", to_station="PT", via_station=None)
    schedule.every().thursday.at("16:00").do(send_message, time="16:29", journeys=1, user_id="UP1H87YA3",
                                             from_station="PT", to_station="UT", via_station=None)
    schedule.every().friday.at("07:00").do(send_message, time="07:51", journeys=1, user_id="UP1H87YA3",
                                           from_station="UT", to_station="PT", via_station=None)
    schedule.every().friday.at("16:00").do(send_message, time="16:29", journeys=1, user_id="UP1H87YA3",
                                           from_station="PT", to_station="UT", via_station=None)

    # Staal:
    schedule.every().monday.at("14:55").do(send_message, time="15:59", journeys=1, user_id="U2UMXJQ7R",
                                           from_station="DT", to_station="UT", via_station="RTD")
    schedule.every().monday.at("14:55").do(send_message, time="15:57", journeys=1, user_id="U2UMXJQ7R",
                                           from_station="DT", to_station="UT", via_station="GVC")
    schedule.every().tuesday.at("16:15").do(send_message, time="17:37", journeys=1, user_id="U2UMXJQ7R",
                                            from_station="UT", to_station="LEDN", via_station="ASDZ")
    schedule.every().wednesday.at("15:05").do(send_message, time="15:59", journeys=1, user_id="U2UMXJQ7R",
                                             from_station="DT", to_station="UT", via_station="RTD")
    schedule.every().wednesday.at("15:05").do(send_message, time="15:57", journeys=1, user_id="U2UMXJQ7R",
                                             from_station="DT", to_station="UT", via_station="GVC")
    schedule.every().thursday.at("15:05").do(send_message, time="15:59", journeys=1, user_id="U2UMXJQ7R",
                                             from_station="DT", to_station="UT", via_station="RTD")
    schedule.every().thursday.at("15:05").do(send_message, time="15:57", journeys=1, user_id="U2UMXJQ7R",
                                             from_station="DT", to_station="UT", via_station="GVC")
    schedule.every().friday.at("15:05").do(send_message, time="15:59", journeys=1, user_id="U2UMXJQ7R",
                                           from_station="DT", to_station="UT", via_station="RTD")
    schedule.every().friday.at("15:05").do(send_message, time="15:57", journeys=1, user_id="U2UMXJQ7R",
                                           from_station="DT", to_station="UT", via_station="GVC")

    print("Starting scheduler...")
    while True:
        schedule.run_pending()
        sleep(1)


if __name__ == '__main__':
    main()
