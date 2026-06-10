import impuls
from argparse import ArgumentParser, Namespace

from kolejki_gtfs.attributions import AddAtributions

from .curate_stops import CurateStops
from .scrape_umapa import LoadUmapa


class KolejkiGTFS(impuls.App):
    def prepare(
        self, args: Namespace, options: impuls.PipelineOptions
    ) -> impuls.Pipeline:
        return impuls.Pipeline(
            tasks=[
                LoadUmapa(),
                CurateStops(),
                impuls.tasks.modify_from_csv.ModifyStopsFromCSV(resource="stops.csv"),
                impuls.tasks.GenerateTripHeadsign(),
                AddAtributions(),
                impuls.tasks.SaveGTFS(
                    headers=GTFS_HEADERS, target="latest.zip", ensure_order=True
                ),
            ],
            resources={
                "stops.csv": impuls.resource.LocalResource("stops.csv"),
            },
            options=options,
        )


GTFS_HEADERS = {
    "agency.txt": (
        "agency_id",
        "agency_name",
        "agency_url",
        "agency_timezone",
    ),
    "stops.txt": (
        "stop_id",
        "stop_name",
        "stop_lat",
        "stop_lon",
    ),
    "routes.txt": (
        "agency_id",
        "route_id",
        "route_short_name",
        "route_long_name",
        "route_type",
    ),
    "trips.txt": (
        "route_id",
        "trip_id",
        "service_id",
        "trip_headsign",
        "trip_short_name",
    ),
    "stop_times.txt": (
        "trip_id",
        "stop_sequence",
        "stop_id",
        "arrival_time",
        "departure_time",
    ),
    "calendar_dates.txt": (
        "service_id",
        "date",
        "exception_type",
    ),
    "feed_info.txt": (
        "feed_publisher_name",
        "feed_publisher_url",
        "feed_lang",
        "feed_version",
    ),
    "attributions.txt": (
        "organization_name",
        "is_producer",
        "is_data_source",
        "attribution_url",
    ),
}
