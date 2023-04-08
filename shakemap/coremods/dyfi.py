# stdlib imports
import json
import os.path
from io import StringIO

# third party imports
import numpy as np
import pandas as pd

# local imports
from shakemap.coremods.base import CoreModule
from shakemap.utils.comcat import get_bytes, get_detail_json
from shakemap.utils.config import get_config_paths
from shakemap.utils.dataframe import dataframe_to_xml

# Get rid of stupid pandas warning
pd.options.mode.chained_assignment = None

# number of seconds to search for event matching origin time
TIMEWINDOW = 60
# distance in decimal degrees to search for event matching coordinates
DEGWINDOW = 0.1
# +/- magnitude threshold to search for matching events
MAGWINDOW = 0.2

required_columns = ["station", "lat", "lon", "network"]
channel_groups = [["[a-z]{2}e", "[a-z]{2}n", "[a-z]{2}z"], ["h1", "h2", "z"], ["unk"]]
pgm_cols = ["pga", "pgv", "psa03", "psa10", "psa30"]
optional = ["location", "distance", "reference", "intensity", "source"]

# what are the DYFI columns and what do we rename them to?
DYFI_COLUMNS_REPLACE = {
    "Geocoded box": "station",
    "CDI": "intensity",
    "Latitude": "lat",
    "Longitude": "lon",
    "No. of responses": "nresp",
    "Hypocentral distance": "distance",
}

OLD_DYFI_COLUMNS_REPLACE = {
    "ZIP/Location": "station",
    "CDI": "intensity",
    "Latitude": "lat",
    "Longitude": "lon",
    "No. of responses": "nresp",
    "Epicentral distance": "distance",
}

MIN_RESPONSES = 1  # minimum number of DYFI responses per grid


class DYFIModule(CoreModule):
    """
    dyfi -- Search ComCat for DYFI data and turn it into a ShakeMap data file.
    """

    command_name = "dyfi"

    def execute(self):
        """
        Write info.json metadata file.

        Raises:
            NotADirectoryError: When the event data directory does not exist.
            FileNotFoundError: When the the shake_result HDF file does not
                exist.
        """
        _, data_path = get_config_paths()
        datadir = os.path.join(data_path, self._eventid, "current")
        if not os.path.isdir(datadir):
            os.makedirs(datadir)

        # try to find the event by our event id
        try:
            detail_json = get_detail_json(self._eventid)
            dataframe, msg = _get_dyfi_dataframe(detail_json)
        except Exception as e:
            fmt = 'Could not retrieve DYFI data for %s - error "%s"'
            self.logger.warning(fmt % (self._eventid, str(e)))
            return

        if dataframe is None:
            self.logger.info(msg)
            return

        reference = "USGS Did You Feel It? System"
        xmlfile = os.path.join(datadir, "dyfi_dat.xml")
        dataframe_to_xml(dataframe, xmlfile, reference)
        self.logger.info("Wrote %i DYFI records to %s" % (len(dataframe), xmlfile))


def _get_dyfi_dataframe(detail_json, inputfile=None, min_nresp=MIN_RESPONSES, rerun_stddev=True):

    if inputfile:
        with open(inputfile, "rb") as f:
            rawdata = f.read()
        if "json" in inputfile:
            df = _parse_geocoded_json(rawdata, min_nresp)
        else:
            df = _parse_geocoded_csv(rawdata, min_nresp)
        if df is None:
            msg = f"Could not read file {inputfile}"

    elif isinstance(detail_json,str):
        # This is a URL, send query to Comcat
        detail_json=get_detail_json(detail_json)
        df, msg = _parse_dyfi_detail(detail_json, min_nresp)

    else:
        df, msg = _parse_dyfi_detail(detail_json, min_nresp)

    if df is None:
        return None, msg

    if rerun_stddev:
        get_stddev(df) # redo stddev calculation

    df["netid"] = "DYFI"
    df["source"] = "USGS (Did You Feel It?)"
    df.columns = df.columns.str.upper()

    return (df, "")


def _parse_dyfi_detail(detail_json, min_nresp):

    if "dyfi" not in detail_json["properties"]["products"]:
        msg = f"Detail for {detail_json['properties']['url']} has no DYFI product at this time."
        dataframe = None
        return (dataframe, msg)

    dyfi = detail_json["properties"]["products"]["dyfi"][0]

    # search the dyfi product, see which of the geocoded
    # files (1km or 10km) it has.  We're going to select the data from
    # whichever of the two has more entries with >= 3 responses,
    # preferring 1km if there is a tie.
    df_1k = pd.DataFrame({"a": []})

    # get 1km data set, if exists
    if "dyfi_geo_1km.geojson" in dyfi["contents"]:
        url = dyfi["contents"]["dyfi_geo_1km.geojson"]["url"]
        bytes_1k = get_bytes(url)
        df_1k = _parse_geocoded_json(bytes_1k, min_nresp)
        return df_1k, ""

    df = df_1k

    if not len(df):
        # try to get a text file data set
        if "cdi_geo.txt" not in dyfi["contents"]:
            return (None, "No geocoded datasets are available for this event.")
        url = dyfi["contents"]["dyfi_geo_1km.geojson"]["url"]
        bytes_geo = get_bytes(url)
        df = _parse_geocoded_csv(bytes_geo, min_nresp)
        return None, "Only cdi_geo.txt found, ignoring."

    return df, ""


def _parse_geocoded_csv(bytes_data, min_nresp):
    # the dataframe we want has columns:
    # 'intensity', 'distance', 'lat', 'lon', 'station', 'nresp'
    # the cdi geo file has:
    # Geocoded box, CDI, No. of responses, Hypocentral distance,
    # Latitude, Longitude, Suspect?, City, State

    # download the text file, turn it into a dataframe

    text_geo = bytes_data.decode("utf-8")
    if text_geo.find("502 Proxy Error"):
        return pd.DataFrame([])
    lines = text_geo.split("\n")
    if not len(lines):
        return pd.DataFrame([])
    columns = lines[0].split(":")[1].split(",")
    columns = [col.strip() for col in columns]

    fileio = StringIO(text_geo)
    df = pd.read_csv(fileio, skiprows=1, names=columns)
    if "ZIP/Location" in columns:
        df = df.rename(index=str, columns=OLD_DYFI_COLUMNS_REPLACE)
    else:
        df = df.rename(index=str, columns=DYFI_COLUMNS_REPLACE)
    df = df.drop(["Suspect?", "City", "State"], axis=1)
    df = df[df["nresp"] >= min_nresp]

    return df


def _parse_geocoded_json(bytes_data, min_nresp):

    text_data = bytes_data.decode("utf-8")
    try:
        jdict = json.loads(text_data)
    except Exception:
        return pd.DataFrame([])
    if len(jdict["features"]) == 0:
        return pd.DataFrame(data={})
    prop_columns = list(jdict["features"][0]["properties"].keys())
    columns = ["lat", "lon"] + prop_columns
    arrays = [[] for col in columns]
    df_dict = dict(zip(columns, arrays))
    for feature in jdict["features"]:
        for column in prop_columns:
            if column == "name":
                prop = feature["properties"][column]
                prop = prop[0 : prop.find("<br>")]
            else:
                prop = feature["properties"][column]

            df_dict[column].append(prop)
        # the geojson defines a box, so let's grab the center point
        lons = [c[0] for c in feature["geometry"]["coordinates"][0]]
        lats = [c[1] for c in feature["geometry"]["coordinates"][0]]
        clon = np.mean(lons)
        clat = np.mean(lats)
        df_dict["lat"].append(clat)
        df_dict["lon"].append(clon)

    df = pd.DataFrame(df_dict)
    df = df.rename(
        index=str, columns={"cdi": "intensity", "dist": "distance", "name": "station"}
    )
    if df is not None:
        df = df[df["nresp"] >= min_nresp]

    return df


def get_stddev(dataframe):
    print(dataframe.columns)
    nresp=dataframe['nresp']
    dataframe['stddev']=stddev_function(nresp)    
    return


# From SM paper, then add 0.2 sigma
def stddev_function(nresp):
    stddev = np.exp(nresp * (-1/24.02)) * 0.25 + 0.09 + 0.2
    stddev = np.round(stddev,4)
    return stddev

