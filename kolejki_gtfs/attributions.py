import impuls
import datetime


class AddAtributions(impuls.Task):
    def execute(self, r: impuls.TaskRuntime) -> None:
        with r.db.transaction():
            r.db.create(
                impuls.model.FeedInfo(
                    publisher_url="https://gtfs.kasznia.net",
                    version=datetime.datetime.now().isoformat(),
                    lang="pl",
                    publisher_name="Marcin Kasznia",
                )
            )

            r.db.create_many(
                impuls.model.Attribution,
                [
                    impuls.model.Attribution(
                        id=1,
                        organization_name="Stop locations © OpenStreetMap contributors under ODbL",
                        is_data_source=True,
                        url="https://openstreetmap.org/copyright",
                    ),
                    impuls.model.Attribution(
                        id="2",
                        organization_name="kasmar00",
                        is_producer=True,
                        url="https://gtfs.kasznia.net",
                    ),
                    impuls.model.Attribution(
                        id="3",
                        organization_name="Kalendarz i rozkład kursowania kolejek/kolei wąskotorowych",
                        is_data_source=True,
                        url="https://www.umapa.pl/kolejki/",
                    ),
                ],
            )
