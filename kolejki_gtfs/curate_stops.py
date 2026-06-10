import impuls
import os
import json
import time
import requests
import slugify

class CurateStops(impuls.Task):
    def execute(self, r: impuls.TaskRuntime) -> None:
        stations = fetch_osm_stations()

        slugify_stations = {slugify.slugify(s["tags"].get("name", "")): s for s in stations}

        with r.db.transaction():
            stops = r.db.retrieve_all(impuls.model.Stop).all()

            for stop in stops:

                osm_station = slugify_stations.get(stop.id)
                if osm_station:
                    stop.lat = osm_station["lat"]
                    stop.lon = osm_station["lon"]
                    r.db.update(stop)
                else:
                    self.logger.warning(f"Could not find OSM station for stop: {stop.name}")
        


def _should_load_from_cache(file) -> bool:
    return os.path.exists(file) and (
        os.path.getmtime(file) > (time.time() - 3600)
    )


def _fetch_osm_with_cache(cache_file: str, query: str):
    if _should_load_from_cache(cache_file):
        print(f"Loading OSM data from cache: {cache_file}")
        with open(cache_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data["elements"]

    print(f"Fetching OSM data from Overpass API for {cache_file}")

    endpoint = "https://overpass-api.de/api/interpreter"
    response = requests.post(
        endpoint,
        data={"data": query},
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "*/*",
            "User-Agent": "Polish Narrow Gauge Railways GTFS Generator (+https://gtfs.kasznia.net)",
        },
    )

    try:
        data = response.json()

        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return data["elements"]

    except ValueError:
        print("Error: Overpass API returned invalid JSON or no data.")
        print("Response text:", response.text)
        exit(1)


def fetch_osm_stations():
    query = """
    [out:json];
    // fetch area “Poland” to search in
    area(id:3600049715)->.searchArea;
    // gather results
    (
      node["railway"="station"]["station"!="light_rail"]["operator:short"!="PKP PLK"]["station"!="subway"](area.searchArea);
      node["railway"="halt"]["operator:short"!="PKP PLK"](area.searchArea);
      node["disused:railway"="station"]["station"!="light_rail"](area.searchArea);
      node["disused:railway"="halt"](area.searchArea);
    );
    // print results
    out geom;
    """
    return _fetch_osm_with_cache("stations-osm.json", query)
