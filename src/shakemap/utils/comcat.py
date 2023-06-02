# stdlib imports
import json
import os.path
from io import StringIO
from urllib.request import urlopen

DETAIL_TEMPLATE = (
    "https://earthquake.usgs.gov/earthquakes/feed/v1.0/detail/[EVENTID].geojson"
)
SCENARIO_TEMPLATE = (
    "https://earthquake.usgs.gov/fdsnws/scenario/1/query?"
    "format=geojson&eventid=[EVENTID]"
)


def get_detail_json(eventid, scenario=False):
    """
    Return the detailed JSON dictionary for a ComCat event ID.
    """
    template = DETAIL_TEMPLATE
    if scenario:
        template = SCENARIO_TEMPLATE
    url = template.replace("[EVENTID]", eventid)
    with urlopen(url, timeout=60) as fh:
        data = fh.read().decode("utf8")
    jdict = json.loads(data)
    return jdict


def get_bytes(url):
    """Get simple bytes from a url."""
    with urlopen(url, timeout=60) as fh:
        data = fh.read()

    return data
