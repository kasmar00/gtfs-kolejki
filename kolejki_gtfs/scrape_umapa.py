from dataclasses import dataclass, field
from logging import exception

import slugify

import impuls
import requests
from bs4 import BeautifulSoup
import re

SCRAPE_BASE = "https://www.umapa.pl/kolejki/"
SCRAPE_CALENDAR = "showcalendar.cgi?railway=1&railway=2&railway=4&railway=16&railway=17&railway=8&railway=9&railway=10&railway=19&railway=11&railway=12&railway=13&railway=15&railway=20&railway=22&railway=5&railway=23&railway=6&railway=25&railway=26"


@dataclass
class StopTime:
    stop_name: str
    arrival_time: str  # in format HH:MM
    departure_time: str  # in format HH:MM


@dataclass
class TrainData:
    train_id: str
    agency_name: str = ""
    train_number: str = ""
    dates: list[str] = field(default_factory=list)  # list of dates in format YYYY-MM-DD
    schedule: list[StopTime] = field(default_factory=list)


class LoadUmapa(impuls.Task):
    agencies = {
        "Bieszczadzka Kolejka Leśna": "BKL",
        "Ełcka Kolej Wąskotorowa": "EKW",
        "Górnośląskie Koleje Wąskotorowe": "GKW",
        "Kolej Wąskotorowa Rogów - Rawa - Biała": "KWRRB",
        "Kolej Wąskotorowa w Rudach": "KWwR",
        "Koszalińska Kolej Wąskotorowa": "TKKW",
        "Krośnicka Kolej Wąskotorowa": "KKW",
        "Maltanka": "Maltanka",
        "Muzeum Kolei Wąskotorowej w Sochaczewie": "MKWwS",
        "Nadmorska Kolej Wąskotorowa": "NKW-R",
        "Nadwiślańska Kolejka Wąskotorowa": "NKW-K",
        "Piaseczyńsko-Grójecka Kolej Wąskotorowa": "PGKW",
        "Przeworska Kolej Dojazdowa": "PKD",
        "Średzka Kolej Powiatowa": "ŚKP",
        "Świętokrzyska Kolejka Dojazdowa": "ŚKD",
        "Wąskotorowe Kolejki Leśne Hajnówka": "WKLH",
        "Wigierska Kolejka Wąskotorowa": "WKW",
        "Wojskowa kolejka wąskotorowa Hel": "WKH",
        "Żnińska Kolej Powiatowa": "ŻKP",
        "Żuławska Kolej Dojazdowa": "ŻKD",
    }

    def execute(self, r: impuls.TaskRuntime) -> None:
        days = self.get_calendar_days()
        self.logger.info(f"Found {len(days)} days in calendar")

        trains: dict[str, TrainData] = {}  # train_id -> train_data
        all_stops: set[str] = set()

        for day_url in days:
            print(day_url)
            date = re.search(r"date=(\d{4}-\d{2}-\d{2})", day_url).group(1)
            self.logger.info(f"Processing day: {date}")
            day_page = requests.get(SCRAPE_BASE + day_url)
            soup = BeautifulSoup(day_page.text, "html.parser")
            train_urls = [
                link.get("href")
                for link in soup.find_all("a")
                if link.get("href") and "singletrain.cgi" in link.get("href")
            ]
            self.logger.info(f"Found {len(train_urls)} trains for day: {date}")
            for href in train_urls:
                train_id = re.search(r"train=(\d+)", href).group(1)
                trains.setdefault(train_id, TrainData(train_id)).dates.append(date)

        for train_id, train_data in trains.items():
            self.logger.info(
                f"Train {train_id} runs on {len(train_data.dates)} days: {train_data.dates}"
            )
            train_page = requests.get(SCRAPE_BASE + f"singletrain.cgi?train={train_id}")
            soup = BeautifulSoup(train_page.text, "html.parser")

            h1 = soup.find("h1")
            if h1:
                match = re.search(r"Rozkład pociągu (\**(.*))", h1.text)
                if match:
                    train_data.train_number = match.group(2)
                else:
                    self.logger.warning(
                        f"Could not extract train ID from H1: {h1.text}"
                    )

            h2 = soup.find("h2")
            if h2:
                train_data.agency_name = h2.text.strip()
            else:
                self.logger.warning(
                    f"Could not find agency name in H2 for train {train_id}"
                )

            train_data.schedule = self.get_stops_for_train(train_id, soup)

            all_stops.update(stop_time.stop_name for stop_time in train_data.schedule)

        for stop in all_stops:
            r.db.create(
                impuls.model.Stop(
                    id=slugify.slugify(stop),
                    name=stop,
                    lat=0.0,
                    lon=0.0,
                )
            )
        for agency_name, agency_id in self.agencies.items():
            r.db.create(
                impuls.model.Agency(
                    id=agency_id,
                    name=agency_name,
                    url="https://www.umapa.pl/kolejki/",
                    timezone="Europe/Warsaw",
                )
            )
            r.db.create(
                impuls.model.Route(
                    id=agency_id,
                    agency_id=agency_id,
                    short_name=agency_id,
                    long_name=agency_name,
                    type=impuls.model.Route.Type.RAIL,
                )
            )
        for train_id, train_data in trains.items():
            self.save_train_data(r, train_data)

    def save_train_data(self, r: impuls.TaskRuntime, train_data: TrainData) -> None:
        with r.db.transaction():
            route_id = self.agencies[train_data.agency_name]

            r.db.create(impuls.model.Calendar(id=train_data.train_id))

            for date in train_data.dates:
                r.db.create(
                    impuls.model.CalendarException(
                        calendar_id=train_data.train_id,
                        date=impuls.model.Date.from_ymd_str(date),
                        exception_type=impuls.model.CalendarException.Type.ADDED,
                    )
                )

            r.db.create(
                impuls.model.Trip(
                    id=train_data.train_id,
                    route_id=route_id,
                    short_name=train_data.train_number,
                    calendar_id=train_data.train_id,
                )
            )

            for i, stop_time in enumerate(train_data.schedule):
                stop_id = slugify.slugify(stop_time.stop_name)

                r.db.create(
                    impuls.model.StopTime(
                        trip_id=train_data.train_id,
                        stop_id=stop_id,
                        arrival_time=impuls.model.TimePoint.from_str(
                            stop_time.arrival_time + ":00"
                        ),
                        departure_time=impuls.model.TimePoint.from_str(
                            stop_time.departure_time + ":00"
                        ),
                        stop_sequence=i,
                    )
                )

    def get_stops_for_train(self, train_id: str, soup: BeautifulSoup) -> list[StopTime]:
        table = soup.find("table")
        if not table:
            self.logger.warning(f"Could not find stops table for train {train_id}")
            return []
        schedule: list[StopTime] = []
        table_rows = iter(table.find_all("tr"))
        while row := next(table_rows, None):
            cells = row.find_all("td")
            if cells[0].get("rowspan") == "2":
                # arrival row
                stop_name = cells[0].text.strip()
                arrival_time = cells[2].text.strip()
                next_row = next(table_rows, None)
                if not next_row:
                    self.logger.warning(
                        f"Could not find departure row for train {train_id}"
                    )
                    continue
                next_cells = next_row.find_all("td")
                departure_time = next_cells[1].text.strip()

                schedule.append(StopTime(stop_name, arrival_time, departure_time))

            else:
                # departure row
                stop_name = cells[0].text.strip()
                time = cells[2].text.strip()

                schedule.append(StopTime(stop_name, time, time))
        return schedule

    def get_calendar_days(self) -> list[str]:

        days = []

        calendar = requests.get(SCRAPE_BASE + SCRAPE_CALENDAR)

        soup = BeautifulSoup(calendar.text, "html.parser")
        for link in soup.find_all("a"):
            href = link.get("href")
            if href and "singleday.cgi" in href:
                days.append(href)
        return days
