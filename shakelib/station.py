# stdlib imports
import copy
import json
import logging
import re
import sqlite3
import xml.etree.ElementTree as ET
from collections import OrderedDict

# third party imports
import numpy as np
import pandas as pd
from gmpacket.packet import GroundMotionPacket
from scipy import constants

# local imports


TABLES = OrderedDict(
    (
        (
            "station",
            OrderedDict(
                (
                    ("id", "text primary key"),  # id is net.sta
                    ("refid", "int"),  # foreign "key" to reference table
                    ("network", "text"),
                    ("code", "text"),
                    ("name", "text"),
                    ("lat", "float"),
                    ("lon", "float"),
                    ("elev", "float"),
                    ("vs30", "float"),
                    ("stddev", "float"),
                    ("instrumented", "int"),
                    ("source", "text"),
                )
            ),
        ),
        ("imt", OrderedDict((("id", "integer primary key"), ("imt_type", "text")))),
        (
            "amp",
            OrderedDict(
                (
                    ("id", "integer primary key"),
                    ("station_id", "text"),
                    ("imt_id", "int"),
                    ("original_channel", "text"),
                    ("orientation", "text"),
                    ("amp", "float"),
                    ("stddev", "float"),
                    ("nresp", "int"),
                    ("flag", "text"),
                )
            ),
        ),
        (
            "reference",
            OrderedDict(
                (
                    ("id", "integer primary key"),
                    ("shortref", "text"),
                    ("longref", "text"),
                    ("description", "text"),
                )
            ),
        ),
    )
)

#
# These are the netid's that indicate MMI data
#
CIIM_TUPLE = ("dyfi", "mmi", "intensity", "ciim")
NON_CHANNEL_COMPONENTS = ["ROTD50.0"]
SUPPORTED_METRICS = ["PGA", "PGV", "SA"]
ORIENTATIONS = {"1": "h", "2": "h", "Z": "v"}
SUPPORTED_SA_PERIODS = [0.3, 1.0, 3.0]


def convert_units(imt_type, input_units, amplitude):
    if re.search(r"PGA|SA", imt_type) is not None:
        # convert to ln(g)
        if input_units in ["cm/s^2", "cm/s**2", "cm/s/s", "gals"]:
            amplitude = np.log(amplitude / constants.g / 100)
        elif input_units in ["m/s^2", "m/s**2", "m/s/s"]:
            amplitude = np.log(amplitude / constants.g)
        elif input_units == "g":
            amplitude = np.log(amplitude)
        elif input_units == "%g":
            amplitude = np.log(amplitude / 100)
        elif input_units in ["ln(g)"]:
            pass
        else:
            raise ValueError(f"Unknown acceleration input units {input_units}")
    elif imt_type == "PGV":
        if input_units in ["cm/s", "cms"]:
            amplitude = np.log(amplitude)
        elif input_units in ["m/s"]:
            amplitude = np.log(amplitude * 100)
        elif input_units in ["ln(cm/s)"]:
            pass
        else:
            raise ValueError(f"Unknown velocity input units {input_units}")
    elif re.search(r"FAS", imt_type) is not None:
        if input_units in ["cm/s", "cms"]:
            amplitude = np.log(amplitude)
        elif input_units in ["m/s"]:
            amplitude = np.log(amplitude * 100)
        elif input_units == "ln(cm/s)":
            pass
        else:
            raise ValueError(f"Unknown FAS input units {input_units}")
    elif re.search(r"DURATION", imt_type) is not None:
        if input_units in ["s", "sec", "seconds"]:
            amplitude = np.log(amplitude)
        elif input_units in ["ln(s)", "ln(sec)", "ln(seconds)"]:
            pass
        else:
            raise ValueError(f"Unknown DURATION input units {input_units}")
    elif imt_type == "ARIAS":
        if input_units in ["cm/s", "cms"]:
            amplitude = np.log(amplitude / 100)
        elif input_units in ["m/s"]:
            amplitude = np.log(amplitude)
        elif input_units in ["ln(m/s)"]:
            pass
        else:
            raise ValueError(f"Unknown velocity input units {input_units}")
    else:
        raise ValueError(f"Unknown imt_type {imt_type}")
    return amplitude


class StationList(object):
    """
    A class to facilitate reading ShakeMap formatted XML fies of peak
    amplitudes and MMI, and
    produce tables of station data. Seismic stations are considered to
    be 'instrumented'; MMI data is not instrumented and is indicated
    in the ShakeMap XML with a ``netid`` attribute of "DYFI," "MMI,"
    "INTENSITY," or "CIIM."

    .. note::
      Typically the user will call the class method :meth:`fromXML`
      to create a :class:`StationList` object the first time
      a set of station files are processed. (Or, as an alternative,
      the user can call :meth:`loadFromXML` and :meth:`fillTables`
      sequentially.)
      This will create a database at the location specified by the
      ``dbfile`` parameter to :meth:`fromXML`. Subsequent programs
      can use the default constructor to simply load ``dbfile``.

    """

    def __init__(self, db):
        """
        The default constructor reads a pre-built SQLite database of
        station data.

        Args:
            dbfile (str):
                A SQLite database file containing pre-processed
                station data.

        Returns:
            A :class:`StationList` object.

        """
        self.db = db
        self.cursor = self.db.cursor()

    def __del__(self):
        """
        Closes out the database when the object is destroyed.
        """
        self.db.commit()
        self.cursor.close()
        self.db.close()

    @classmethod
    def loadFromSQL(cls, sql, dbfile=":memory:"):
        """
        Create a new object from saved SQL code (see :meth:`dumpToSQL`).

        Args:
            sql (str):
                SQL code to create and populate the database
            dbfile (str):
                The path to a file in which the database will reside.
                The default is ':memory:' for an in-memory database.

        Returns:
            :class:`Stationlist` object.
        """
        db = sqlite3.connect(dbfile, timeout=15)
        self = cls(db)
        self.cursor.executescript(sql)
        return self

    def dumpToSQL(self):
        """
        Dump the database as a string of SQL code (see :meth:`loadFromSQL`).

        Args:
            None

        Returns:
            A string of SQL sufficient to restore and repopulate the
            database.
        """

        return "\n".join(list(self.db.iterdump()))

    @classmethod
    def loadFromFiles(cls, filelist, min_nresp=3, dbfile=":memory:"):
        """
        Create a StationList object by reading one or more ShakeMap XML or
        JSON input files.

        Args:
            filelist (sequence of str):
                Sequence of ShakeMap XML and/or JSON input files to read.
            min_nresp (int):
                The minimum number of DYFI observations required to form and valid
                observation. Default is 3.
            dbfile (str):
                Path to a file into which to write the SQLite database.
                The default is ':memory:' for an in-memory database.

        Returns:
            :class:`StationList` object
        """
        # Create the database and tables
        db = sqlite3.connect(dbfile, timeout=15)
        self = cls(db)
        self._createTables()
        self.addData(filelist, min_nresp)
        return self

    def addData(self, filelist, min_nresp):
        """
        Add data from XML or JSON files to the existing StationList.

        Args:
            filelist:
                A list of ShakeMap XML or JSON input files.
            min_nresp (int):
                The minimum number of DYFI observations required to form and valid
                observation.

        Returns:
            nothing: Nothing.
        """
        jsonfiles = [x for x in filelist if x.endswith(".json")]
        xmlfiles = [x for x in filelist if x.endswith(".xml")]
        if len(jsonfiles):
            self._loadFromJSON(jsonfiles, min_nresp)
        if len(xmlfiles):
            self._loadFromXML(xmlfiles, min_nresp)
        return self

    def _loadFromXML(self, xmlfiles, min_nresp):
        """
        Create a StationList object by reading one or more ShakeMap XML input
        files.

        Args:
            xmlfiles (sequence of str):
                Sequence of ShakeMap XML input files to read.
            min_nresp (int):
                The minimum number of DYFI responses for an observation to be
                included in the station output.

        Returns:
            nothing: Nothing.
        """
        # Parse the xml into a dictionary
        stationdict = {}
        imtset = set()
        for xmlfile in xmlfiles:
            stationdict, ims = self._filter_station(xmlfile, stationdict, min_nresp)
            imtset |= ims
        # fill the database and create the object from it
        self._loadFromDict(stationdict, imtset)
        self._fixOrientations()
        return

    def _parse_shakemap_json(self, jfile, min_nresp, sta_set, imt_set, amp_set):
        with open(jfile, "r") as jfp:
            stas = json.load(jfp)

        if "type" not in stas:
            logging.warn(f"{jfile} appears to contain no stations, skipping")
            return ([], [], [])
        if stas["type"] != "FeatureCollection":
            logging.warn(f"{jfile} is not a ShakeMap JSON stationlist, skipping")
            return ([], [], [])

        # if present, insert reference stuff into the database
        reference_rows = []
        if "references" in stas:
            for shortref, refdict in stas["references"].items():
                longref = refdict["long_reference"]
                description = refdict["description"]
                reference_rows.append([shortref, longref, description])

        station_rows = []
        amp_rows = []
        for feature in stas["features"]:
            sta_id = feature["id"]
            if sta_id in sta_set:
                continue
            else:
                sta_set.add(sta_id)
            lon = feature["geometry"]["coordinates"][0]
            lat = feature["geometry"]["coordinates"][1]
            netid = feature["properties"]["network"]
            code = sta_id.replace(netid + ".", "")
            network = feature["properties"]["network"]
            name = feature["properties"].get("name", None)
            elev = feature["properties"].get("elev", None)
            vs30 = feature["properties"].get("vs30", None)
            source = feature["properties"].get("source", None)
            refid = feature["properties"].get("refid", None)
            stddev = 0

            # is this an intensity observation or an instrument?
            instrumented = int(netid.lower() not in CIIM_TUPLE)

            station_rows.append(
                (
                    sta_id,
                    network,
                    code,
                    name,
                    lat,
                    lon,
                    elev,
                    vs30,
                    stddev,
                    instrumented,
                    source,
                    refid,
                )
            )

            if not instrumented:
                try:
                    amplitude = float(feature["properties"].get("intensity", np.nan))
                except (ValueError, TypeError):
                    amplitude = np.nan
                try:
                    stddev = float(
                        feature["properties"].get("intensity_stddev", np.nan)
                    )
                except (ValueError, TypeError):
                    stddev = np.nan
                try:
                    nresp = int(feature["properties"].get("nresp", -1))
                except (ValueError, TypeError):
                    nresp = -1
                if nresp >= 0 and nresp < min_nresp:
                    continue
                flag = feature["properties"]["intensity_flag"]
                if not flag or flag == "":
                    flag = "0"
                amp_rows.append(
                    [sta_id, "MMI", "mmi", "h", amplitude, stddev, flag, nresp]
                )
                imt_set.add("MMI")
                continue

            #
            # Collect the channel names for this station to see if we
            # can resolve the orientation of any of the channels ending
            # with "1" or "2".
            #
            chan_names = []
            for comp in feature["properties"]["channels"]:
                chan_names.append(comp["name"])
            # Some legacy data stupidly names the channel the same as the
            # station name. If there is only one channel, and its name
            # is the station name, we assume it's horizontal and move on.
            if len(chan_names) == 1 and chan_names[0] == name:
                orients = ["H"]
            else:
                orients = _getOrientationSet(chan_names)
            #
            # Now insert the amps into the database
            #
            for ic, comp in enumerate(feature["properties"]["channels"]):
                original_channel = comp["name"]
                orientation = orients[ic]
                for amp in comp["amplitudes"]:
                    imt_type = amp["name"].upper()
                    imt_set.add(imt_type)
                    amp_id = sta_id + "." + imt_type + "." + original_channel
                    if amp_id in amp_set:
                        continue
                    amp_set.add(amp_id)
                    amplitude = amp["value"]
                    if "ln_sigma" in amp:
                        stddev = amp["ln_sigma"]
                    elif "sigma" in amp:
                        stddev = amp["sigma"]
                    else:
                        stddev = 0
                    flag = amp["flag"]
                    units = amp["units"]
                    if (
                        amplitude == "null"
                        or np.isnan(float(amplitude))
                        or amplitude <= 0
                    ):
                        amplitude = "NULL"
                        flag = "G"
                    elif imt_type == "MMI":
                        pass
                    else:
                        amplitude = convert_units(imt_type, units, amplitude)
                    amp_rows.append(
                        [
                            sta_id,
                            imt_type,
                            original_channel,
                            orientation,
                            amplitude,
                            stddev,
                            flag,
                            -1,
                        ]
                    )
        return (station_rows, amp_rows, reference_rows)

    def _parse_groundpacket_json(self, jsonfile, sta_set, imt_set, amp_set):
        packet = GroundMotionPacket.load_from_json(jsonfile)
        station_rows = []
        amp_rows = []
        reference_rows = []
        for feature in packet.features:
            network_code = feature.properties.network_code
            station_code = feature.properties.station_code
            station_id = f"{network_code}.{station_code}"
            if station_id in sta_set:
                continue
            else:
                sta_set.add(station_id)
            station_name = feature.properties.name
            station_lon, station_lat, station_elev = feature.geometry.coordinates
            vs30 = None
            station_rows.append(
                (
                    station_id,
                    network_code,
                    station_code,
                    station_name,
                    station_lat,
                    station_lon,
                    station_elev,
                    vs30,
                    0.0,
                    1,
                    None,
                    None,
                )
            )
            for stream in feature.properties.streams:
                for trace in stream.traces:
                    channel_code = trace.properties.channel_code
                    location_code = trace.properties.location_code
                    if not len(location_code.strip()):
                        location_code = "--"
                    if channel_code in NON_CHANNEL_COMPONENTS:
                        continue

                    orient = ORIENTATIONS[channel_code[-1]]
                    orientation = _getOrientation(channel_code, orient)

                    for metric in trace.metrics:
                        imt_type = metric.properties.name
                        if imt_type not in SUPPORTED_METRICS:
                            continue

                        stddev = 0.0
                        if isinstance(metric.values, float):
                            amplitude = metric.values
                            amplitude = convert_units(
                                imt_type, metric.properties.units, amplitude
                            )
                            flag = 0
                            nresp = -1
                            imt_set.add(imt_type)
                            amp_rows.append(
                                [
                                    station_id,
                                    imt_type,
                                    f"{channel_code}",
                                    orientation,
                                    amplitude,
                                    stddev,
                                    flag,
                                    nresp,
                                ]
                            )
                        else:
                            for idx, amplitude in enumerate(metric.values[0]):
                                amplitude = convert_units(
                                    imt_type, metric.properties.units, amplitude
                                )
                                period = metric.dimensions.axis_values[1][idx]
                                if period not in SUPPORTED_SA_PERIODS:
                                    continue
                                imt_type = f"{metric.properties.name}({period:.1f})"
                                imt_set.add(imt_type)
                                amp_id = (
                                    f"{network_code}.{station_code}.{imt_type}."
                                    f"{location_code}.{channel_code}"
                                )
                                if amp_id in amp_set:
                                    continue
                                amp_set.add(amp_id)
                                amp_rows.append(
                                    [
                                        station_id,
                                        imt_type,
                                        f"{channel_code}",
                                        orientation,
                                        amplitude,
                                        stddev,
                                        flag,
                                        nresp,
                                    ]
                                )
        return (station_rows, amp_rows, reference_rows)

    def _loadFromJSON(self, jsonfiles, min_nresp):
        """
        Create a StationList object by reading one or more ShakeMap JSON
        data files.

        Args:
            jsonfiles (sequence of str):
                Sequence of ShakeMap JSON data files to read.
            min_nresp (int):
                The minimum number of DYFI responses for an observation to be
                included in the station output.

        Returns:
            nothing: Nothing.
        """

        #
        # Get the station codes for all the stations in the db
        #
        query = "SELECT id FROM station"
        self.cursor.execute(query)
        sta_set = set([z[0] for z in self.cursor.fetchall()])

        orig_imt_set = self.getIMTtypes()
        imt_set = orig_imt_set.copy()

        amp_set = set()
        station_rows = []
        amp_rows = []
        ref_rows = []
        for jfile in jsonfiles:
            try:
                _ = GroundMotionPacket.load_from_json(jfile)
                tstations, tamps, trefs = self._parse_groundpacket_json(
                    jfile, sta_set, imt_set, amp_set
                )
            except Exception:
                tstations, tamps, trefs = self._parse_shakemap_json(
                    jfile, min_nresp, sta_set, imt_set, amp_set
                )
            station_rows += tstations
            amp_rows += tamps
            ref_rows += trefs

        new_imts = imt_set - orig_imt_set
        if any(new_imts):
            self.cursor.executemany(
                "INSERT INTO imt (imt_type) VALUES (?)", zip(new_imts)
            )
            self.db.commit()
        query = "SELECT imt_type, id FROM imt"
        self.cursor.execute(query)
        imt_hash = dict(self.cursor.fetchall())

        for row in amp_rows:
            row[1] = imt_hash[row[1]]

        self.cursor.executemany(
            "INSERT INTO amp (station_id, imt_id, original_channel, "
            "orientation, amp, stddev, flag, nresp) VALUES "
            "(?, ?, ?, ?, ?, ?, ?, ?)",
            amp_rows,
        )
        self.db.commit()

        self.cursor.executemany(
            "INSERT INTO station (id, network, code, name, lat, lon, "
            "elev, vs30, stddev, instrumented, source, refid) VALUES "
            "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            station_rows,
        )
        self.db.commit()

        self.cursor.executemany(
            "INSERT INTO reference (shortref, longref, description) VALUES "
            "(?, ?, ?)",
            ref_rows,
        )

    def getGeoJson(self):
        jdict = {"type": "FeatureCollection", "features": []}
        query = "SELECT id, shortref, longref, description FROM reference"
        self.cursor.execute(query)
        rows = self.cursor.fetchall()
        if len(rows):
            refdict = {}
            for row in rows:
                refid = row[0]
                shortref = row[1]
                longref = row[2]
                description = row[3]
                refdict[refid] = {
                    "refid": refid,
                    "long_reference": longref,
                    "short_reference": shortref,
                    "description": description,
                }
            jdict["references"] = refdict
        self.cursor.execute(
            "SELECT id, network, code, name, lat, lon, elev, vs30, "
            "instrumented, source, refid from station"
        )
        sta_rows = self.cursor.fetchall()

        for sta in sta_rows:
            feature = {
                "type": "Feature",
                "id": sta[0],
                "properties": {
                    "code": str(sta[2]),
                    "name": sta[3],
                    "refid": sta[10],
                    "instrumentType": "UNK" if sta[8] == 1 else "OBSERVED",
                    "source": sta[9],
                    "network": sta[1],
                    "commType": "UNK",
                    "location": "",
                    "intensity": None,
                    "intensity_flag": "",
                    "intensity_stddev": None,
                    "pga": None,
                    "pgv": None,
                    "distance": None,
                    "elev": sta[6],
                    "vs30": sta[7],
                    "channels": [],
                },
                "geometry": {"type": "Point", "coordinates": [sta[5], sta[4]]},
            }
            self.cursor.execute(
                "SELECT a.amp, i.imt_type, a.original_channel, "
                "a.flag, a.stddev, a.orientation, a.nresp "
                "FROM amp a, imt i "
                'WHERE a.station_id = "%s" '
                "AND a.imt_id = i.id" % (str(sta[0]))
            )
            amp_rows = self.cursor.fetchall()
            if sta[8] == 0:
                if len(amp_rows) != 1:
                    logging.warn("Couldn't find intensity for MMI station.")
                    continue
                feature["properties"]["intensity"] = amp_rows[0][0]
                feature["properties"]["intensity_stddev"] = amp_rows[0][4]
                feature["properties"]["intensity_flag"] = amp_rows[0][3]
                feature["properties"]["nresp"] = amp_rows[0][6]
                feature["properties"]["channels"] = []
                jdict["features"].append(feature)
                continue

            channels = {}
            for amp in amp_rows:
                sd_string = "ln_sigma"
                if amp[2] not in channels:
                    channels[amp[2]] = {"name": amp[2], "amplitudes": []}
                if amp[0] == "NULL":
                    value = "null"
                    sigma = "null"
                else:
                    value = amp[0]
                    sigma = float(f"{amp[4]:.4f}")
                if amp[1] == "PGV":
                    if value != "null":
                        value = float(f"{np.exp(value):.4f}")
                    units = "cm/s"
                elif amp[1] == "MMI":
                    if value != "null":
                        value = float(f"{value:.1f}")
                    units = "intensity"
                    sd_string = "sigma"
                else:
                    if value != "null":
                        value = float(f"{np.exp(value) * 100:.4f}")
                    units = "%g"
                aflag = str(amp[3])
                if "I" in aflag and "IncompleteRecord" not in aflag:
                    aflag = aflag.replace("I", "IncompleteRecord")
                if "G" in aflag and "Glitch" not in aflag:
                    aflag = aflag.replace("G", "Glitch")
                if "T" in aflag and "Outlier" not in aflag:
                    aflag = aflag.replace("T", "Outlier")
                if "M" in aflag and "ManuallyFlagged" not in aflag:
                    aflag = aflag.replace("M", "ManuallyFlagged")
                if amp[5] == "U":
                    if aflag == "0":
                        aflag = "UnknownOrientation"
                    else:
                        aflag = str(amp[3]) + ",UnknownOrientation"
                this_amp = {
                    "name": amp[1].lower(),
                    "value": value,
                    "units": units,
                    "flag": aflag,
                    sd_string: sigma,
                }
                channels[amp[2]]["amplitudes"].append(this_amp)
            for channel in channels.values():
                feature["properties"]["channels"].append(channel)
            jdict["features"].append(feature)

        return jdict

    def _loadFromDict(self, stationdict, imtset):
        """
        Internal method to turn the station dictionary created from the
        ShakeMap XML input files into a SQLite database.

        Args:
            stationdictlist (list of stationdicts):
                A list of station dictionaries returned by _filter_station().
            dbfile (string):
                The path to which the SQLite database will be written.

        Returns:
            :class:`StationList` object
        """
        #
        # Get the current IMTs and their IDs and add any new ones
        #
        imts_in_db = self.getIMTtypes()
        new_imts = imtset - imts_in_db
        if any(new_imts):
            self.cursor.executemany(
                "INSERT INTO imt (imt_type) VALUES (?)", zip(new_imts)
            )
            self.db.commit()

        # Now get the updated list of IMTs and their IDs
        query = "SELECT imt_type, id FROM imt"
        self.cursor.execute(query)
        imt_hash = dict(self.cursor.fetchall())

        #
        # Get the station codes for all the stations in the db
        #
        query = "SELECT id FROM station"
        self.cursor.execute(query)
        sta_set = set([z[0] for z in self.cursor.fetchall()])

        #
        # Insert any new stations into the station table
        #
        station_rows = []
        for sta_id, station_tpl in stationdict.items():
            if sta_id in sta_set:
                continue
            else:
                sta_set.add(sta_id)
            station_attributes, comp_dict = station_tpl
            lat = station_attributes["lat"]
            lon = station_attributes["lon"]
            code = station_attributes["code"]
            # the attributes dictionary may not have the same
            # netid that we created. Use instead the first part of
            # the station id
            netid = sta_id[0 : sta_id.find(".")]
            network = netid
            name = station_attributes.get("name", None)
            elev = station_attributes.get("elev", None)
            vs30 = station_attributes.get("vs30", None)
            stddev = station_attributes.get("stddev", 0)
            source = station_attributes.get("source", None)
            refid = station_attributes.get("refid", None)

            instrumented = int(network.lower() not in CIIM_TUPLE)

            station_rows.append(
                (
                    sta_id,
                    network,
                    code,
                    name,
                    lat,
                    lon,
                    elev,
                    vs30,
                    stddev,
                    instrumented,
                    source,
                    refid,
                )
            )

        self.cursor.executemany(
            "INSERT INTO station (id, network, code, name, lat, lon, "
            "elev, vs30, stddev, instrumented, source, refid) VALUES "
            "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            station_rows,
        )
        self.db.commit()

        #
        # Now add the amps, first get the current set so we don't add
        # any duplicates; a unique amp will be (station_id, imt_id,
        # original_channel)
        #
        query = "SELECT station_id, imt_id, original_channel FROM amp"
        self.cursor.execute(query)
        amp_rows = self.cursor.fetchall()
        # Create a unique identifier for each amp so we don't repeat any
        amp_set = set([str(v[0]) + "." + str(v[1]) + "." + str(v[2]) for v in amp_rows])

        #
        # Insert the amps for each component
        #
        amp_rows = []
        for sta_id, station_tpl in stationdict.items():
            station_attributes, comp_dict = station_tpl
            instrumented = int(station_attributes["netid"].lower() not in CIIM_TUPLE)
            for original_channel, cdict in comp_dict.items():
                pgm_dict = cdict["amps"]
                if len(comp_dict) == 1 and original_channel == station_attributes.get(
                    "name", ""
                ):
                    orientation = "H"
                else:
                    orientation = cdict["attrs"].get("orientation", None)
                    orientation = _getOrientation(original_channel, orientation)
                for imt_type, imt_dict in pgm_dict.items():
                    if (instrumented == 0) and (imt_type != "MMI"):
                        continue
                    imtid = imt_hash[imt_type]
                    amp_id = (
                        str(sta_id) + "." + str(imtid) + "." + str(original_channel)
                    )
                    if amp_id in amp_set:
                        continue
                    else:
                        amp_set.add(amp_id)
                    amp = imt_dict["value"]
                    units = imt_dict["units"]
                    stddev = imt_dict["stddev"]
                    flag = imt_dict["flag"]
                    nresp = imt_dict.get("nresp", -1)
                    if np.isnan(amp):
                        amp = "NULL"
                        flag = "G"
                    elif imt_type == "MMI":
                        if amp <= 0:
                            amp = "NULL"
                            flag = "G"
                        else:
                            pass
                    elif imt_type == "PGV":
                        if units == "cm/s":
                            if amp <= 0:
                                amp = "NULL"
                                flag = "G"
                            else:
                                amp = np.log(amp)
                        elif units == "ln(cm/s)":
                            pass
                        else:
                            raise ValueError(f"Unknown units {units} in input")
                    else:
                        if units == "%g":
                            if amp <= 0:
                                amp = "NULL"
                                flag = "G"
                            else:
                                amp = np.log(amp / 100.0)
                        elif units == "ln(g)":
                            pass
                        else:
                            raise ValueError(f"Unknown units {units} in input")

                    amp_rows.append(
                        (
                            sta_id,
                            imtid,
                            original_channel,
                            orientation,
                            amp,
                            stddev,
                            flag,
                            nresp,
                        )
                    )

        self.cursor.executemany(
            "INSERT INTO amp (station_id, imt_id, original_channel, "
            "orientation, amp, stddev, flag, nresp) VALUES "
            "(?, ?, ?, ?, ?, ?, ?, ?)",
            amp_rows,
        )
        self.db.commit()
        return

    def getIMTtypes(self):
        """
        Return a set of IMT types found in the database

        Args:
            None

        Returns:
            A set of IMT types
        """
        self.cursor.execute("SELECT imt_type FROM imt")
        return set([z[0] for z in self.cursor.fetchall()])

    def getStationDictionary(self, instrumented=True, min_nresp=1):
        """
        Return a dictionary of the instrumented or non-instrumented
        stations. The keys describe the parameter, the values are Numpy
        arrays of the parameter in question.

        For the standard set of ShakeMap IMTs (mmi, pga, pgv, psa03, psa10,
        psa30), the keys in the dictionary would be:

        'id', 'network', 'code', 'name', 'lat', 'lon', 'elev', 'vs30',
        'stddev', 'instrumented', 'PGA', 'PGA_sd', 'PGV', 'PGA_sd',
        'SA(0.3)', 'SA(0.3)_sd, 'SA(1.0)', 'SA(1.0)_sd', 'SA(3.0)',
        'SA(3.0)_sd'

        For the non-instrumented dictionary, the keys would be:

        'id', 'network', 'code', 'name', 'lat', 'lon', 'elev', 'vs30',
        'stddev', 'instrumented', 'MMI', 'MMI_sd', 'nresp'

        The **id** column is **network** and **code** concatenated with a
        period (".") between them.

        All ground motion units are natural log units. Distances are in km.

        Args:
            instrumented (bool):
                Set to True if the dictionary is to contain the instrumented
                stations, or to False if the dictionary is to contain the
                non-instrumented (MMI) stations.
            min_nresp (int):
                The minimum number of DYFI responses required to make a valid
                observation.

        Returns:
            dict, set: A dictionary of Numpy arrays, and a set specifying
            the IMTs found in the dictionary.

        Raises:
            TypeError: if "instrumented" argument is not type bool.
        """

        if not isinstance(instrumented, bool):
            raise TypeError(
                "getStationDictionary: the instrumented argument "
                "must be of type bool"
            )
        columns = list(TABLES["station"].keys())
        dstr = ", ".join(columns)
        self.cursor.execute(
            "SELECT %s FROM station where instrumented = %d" % (dstr, instrumented)
        )

        station_rows = self.cursor.fetchall()
        nstation_rows = len(station_rows)
        if not nstation_rows:
            return None, set()
        station_columns = list(zip(*station_rows))
        df = OrderedDict()
        for ic, col in enumerate(columns):
            df[col] = np.array(station_columns[ic])

        myimts = set()
        for imt in self.getIMTtypes():
            if (instrumented and "MMI" in imt) or (
                not instrumented and "MMI" not in imt
            ):
                continue
            df[imt] = np.full(nstation_rows, np.nan)
            df[imt + "_sd"] = np.full(nstation_rows, 0.0)
            if instrumented is False:
                df[imt + "_nresp"] = np.full(nstation_rows, -1, dtype=np.int32)
            myimts.update([imt])

        id_dict = dict(zip(df["id"], range(nstation_rows)))

        #
        # Get all of the unflagged amps with the proper orientation
        #
        self.cursor.execute(
            "SELECT a.amp, i.imt_type, a.station_id, a.stddev, a.nresp  FROM "
            'amp a, station s, imt i WHERE a.flag = "0" '
            "AND s.id = a.station_id "
            "AND a.imt_id = i.id "
            'AND s.instrumented = ? AND a.orientation NOT IN ("Z", "U") '
            "AND a.amp IS NOT NULL "
            "AND (a.nresp < 0 OR a.nresp >= ?)",
            (
                instrumented,
                min_nresp,
            ),
        )
        amp_rows = self.cursor.fetchall()

        #
        # Go through all the amps and put them into the data frame
        #
        for this_row in amp_rows:
            #
            # Set the cell to the peak amp
            #
            rowidx = id_dict[this_row[2]]
            cval = df[this_row[1]][rowidx]
            amp = this_row[0]
            stddev = this_row[3]
            nresp = this_row[4]
            if np.isnan(cval) or (cval < amp):
                df[this_row[1]][rowidx] = amp
                df[this_row[1] + "_sd"][rowidx] = stddev
                if instrumented is False:
                    df[this_row[1] + "_nresp"][rowidx] = nresp

        return df, myimts

    def _fixOrientations(self):
        """
        Look for stations with channels that have orientations "1", "2",
        and "Z", and set the "1" and "2" channels to have horizontal
        orientation.
        """
        sql = (
            "SELECT DISTINCT station_id, original_channel "
            "FROM amp "
            "WHERE orientation IN ('U', 'Z') "
            "ORDER BY station_id"
        )
        self.cursor.execute(sql)
        sta_rows = self.cursor.fetchall()
        current_station_id = ""
        channel_list = []
        for row in sta_rows:
            station_id, channel = row
            if current_station_id == "":
                current_station_id = station_id
                channel_list = [channel]
            elif station_id == current_station_id:
                channel_list.append(channel)
            if len(channel_list) == 3:
                ochars = [x[-1] for x in channel_list]
                if "1" in ochars and "2" in ochars and "Z" in ochars:
                    hinds = [i for i, x in enumerate(ochars) if x == "1" or x == "2"]
                    sql = (
                        "UPDATE amp "
                        'SET orientation = "H"'
                        "WHERE station_id = ? "
                        "AND original_channel IN (?, ?)"
                    )
                    self.cursor.execute(
                        sql,
                        (
                            current_station_id,
                            channel_list[hinds[0]],
                            channel_list[hinds[1]],
                        ),
                    )
                    self.db.commit()
                # 3 channels, but not 1, 2, Z: bummer
                channel_list = []
            # Channels weren't 3 so we can't fix; bummer
            if current_station_id != station_id:
                current_station_id = station_id
                channel_list = [channel]
        return

    @staticmethod
    def _getGroundMotions(comp, imt_translate):
        """
        Get a dictionary of peak ground motions (values and flags).
        Output keys are one of: [pga,pgv,psa03,psa10,psa30]
        Even if flags are not specified in the input, they will
        be guaranteed to at least have a flag of '0'.
        """
        pgmdict = {}
        imtset = set()
        for pgm in comp:
            if pgm.tag == "#text":
                continue
            key = pgm.tag
            if key not in imt_translate:
                if key in ("acc", "pga"):
                    new_key = "PGA"
                elif key in ("vel", "pgv"):
                    new_key = "PGV"
                elif "mmi" in key:
                    new_key = "MMI"
                elif "psa" in key:
                    pp = get_imt_period(key)
                    new_key = "SA(" + str(pp) + ")"
                else:
                    raise ValueError(f"Unknown amp type in input: {key}")
                imt_translate[key] = new_key
            else:
                new_key = imt_translate[key]
            key = new_key

            if "value" in pgm.attrib:
                try:
                    value = float(pgm.attrib["value"])
                except (ValueError, TypeError):
                    logging.warn(
                        "Unknown value in XML: %s for amp: %s"
                        % (pgm.attrib["value"], pgm.tag)
                    )
                    continue
            else:
                logging.warn(f"No value for amp {pgm.tag}")
                continue
            if "flag" in pgm.attrib and pgm.attrib["flag"] != "":
                flag = pgm.attrib["flag"]
            else:
                flag = "0"
            if "ln_stddev" in pgm.attrib:
                stddev = float(pgm.attrib["ln_stddev"])
            else:
                stddev = 0
            if "units" in pgm.attrib:
                units = pgm.attrib["units"]
            else:
                if key == "PGV":
                    units = "cm/s"
                elif key == "MMI":
                    units = "intensity"
                else:
                    units = "%g"
            pgmdict[key] = {
                "value": value,
                "flag": flag,
                "stddev": stddev,
                "units": units,
            }
            imtset.add(key)
        return pgmdict, imtset, imt_translate

    def _filter_station(self, xmlfile, stationdict, min_nresp):
        """
        Filter individual xmlfile into a stationdict data structure.

        Args:
            xmlfile (string):
                Path to ShakeMap XML input file (or file-like object)
                containing station data.
            stationdict (dict):
                the dictionary of stations that the stations in this file should
                be added to.
            min_nresp (int):
                The minimum number of responses that a DYFI observation needs
                to be included in the processing.

        Returns:
            stationdict data structure
            imts: a set of IMTs that were found in the file
        """
        #
        # Strip off any namespace garbage that is prepended
        # to the tags
        #
        it = ET.iterparse(xmlfile)
        for _, el in it:
            if "}" in el.tag:
                el.tag = el.tag.split("}", 1)[1]
        #
        # Parse the cleaned up xml tree
        #
        imt_translate = {}
        imtset = set()
        root = it.root
        for sl in root.iter("stationlist"):
            if "reference" in sl.attrib:
                longref = sl.attrib["reference"]
                shortref = ""
                description = ""
                query = (
                    f"INSERT INTO reference "
                    "(shortref, longref, description) VALUES "
                    f'("{shortref}","{longref}","{description}")'
                )
                self.cursor.execute(query)
                self.db.commit()
                query = f"SELECT id FROM reference WHERE longref is " f'("{longref}")'
                self.cursor.execute(query)
                row = self.cursor.fetchall()
                refid = row[0][0]
            else:
                refid = None
            for station in sl:
                if station.tag != "station":
                    continue
                # look at the station attributes to figure out if this is a
                # DYFI-type station or a station with instruments measuring
                # PGA, PGV, etc.
                attributes = station.attrib.copy()
                if "netid" in attributes:
                    netid = attributes["netid"]
                    if not len(netid.strip()):
                        netid = "unknown"
                else:
                    netid = "unknown"
                attributes["netid"] = netid
                attributes["refid"] = refid
                instrumented = int(netid.lower() not in CIIM_TUPLE)

                if "code" not in attributes:
                    logging.warn("Station does not have station code: skipping")
                    continue
                code = attributes["code"]
                if code.startswith(netid + "."):
                    sta_id = code
                    code = code.replace(netid + ".", "")
                    attributes["code"] = code
                else:
                    sta_id = netid + "." + code

                if sta_id in stationdict:
                    compdict = stationdict[sta_id][1]
                else:
                    compdict = {}
                for comp in station:
                    if "name" not in comp.attrib:
                        logging.warn(
                            f"Unnamed component for station {sta_id}; skipping"
                        )
                        continue
                    compname = comp.attrib["name"]
                    if "Intensity Questionnaire" in str(compname):
                        compdict["mmi"] = {"amps": {}, "attrs": {}}
                        continue
                    tpgmdict, ims, imt_translate = self._getGroundMotions(
                        comp, imt_translate
                    )
                    if compname in compdict:
                        pgmdict = compdict[compname]["amps"]
                    else:
                        pgmdict = {}
                    pgmdict.update(tpgmdict)
                    # copy the VALUES, not REFERENCES, of the component list
                    # into our growing dictionary
                    compdict[compname] = {
                        "attrs": copy.copy(comp.attrib),
                        "amps": copy.copy(pgmdict),
                    }
                    imtset |= ims
                if ("intensity" in attributes) and (instrumented == 0):
                    if "mmi" not in compdict:
                        compdict["mmi"] = {"amps": {}, "attrs": {}}
                    if "intensity_flag" in attributes:
                        flag = attributes["intensity_flag"]
                    else:
                        flag = "0"
                    if "intensity_stddev" in attributes:
                        stddev = float(attributes["intensity_stddev"])
                    else:
                        stddev = 0
                    if "nresp" in attributes:
                        nresp = int(attributes["nresp"])
                    else:
                        nresp = -1
                    if nresp >= 0 and nresp < min_nresp:
                        continue
                    compdict["mmi"]["amps"]["MMI"] = {
                        "value": float(attributes["intensity"]),
                        "stddev": stddev,
                        "nresp": nresp,
                        "flag": flag,
                        "units": "intensity",
                    }
                    imtset.add("MMI")
                stationdict[sta_id] = (attributes, copy.copy(compdict))
        return stationdict, imtset

    def _createTables(self):
        """
        Build the database tables.
        """
        for table in TABLES.keys():
            sql = f"CREATE TABLE {table} ("
            nuggets = []
            for column, ctype in TABLES[table].items():
                nuggets.append(f"{column} {ctype}")
            sql += ",".join(nuggets) + ")"
            self.cursor.execute(sql)

        self.db.commit()
        return


def get_imt_period(imt):
    """
    Get the period from a string like psa3p0, psa3.0, or psa30 (the first
    being favored). Return the floating point period.

    Args:
        imt (str): a string starting with "psa" and ending with something
            that can reasonably be converted to a floating point number.

    Returns:
        float: The period of the psa input.

    TODO: Could do a lot more error checking here, but I guess we're
    assuming that the people who send us data aren't idiots.
    """
    # Updated 'psa2p5' style
    p = re.search(r"(?<=psa).*", imt)
    if "p" in p.group(0):
        return float(p.group(0).replace("p", "."))
    # Weird, but we'll allow it psa2.5 style
    if "." in p.group(0):
        return float(p.group(0))
    # Old school psa25 style
    p = re.search(r"(?<=psa)\d+", imt)
    return float(p.group(0)[:-1] + "." + p.group(0)[-1])


def _getOrientation(orig_channel, orient):
    """
    Return a character representing the orientation of a channel.

    Args:
        orig_channel (string):
            String representing the seed channel (e.g. 'HNZ'). The
            final character is assumed to be the (uppercase) orientation.
        orient (str or None):
            Gives the orientation of the channel, overriding channel
            codes that end in numbers. Must be one of 'h' (horizontal)
            or 'v' (vertical), or None if the orientation has not been
            explicitly specified in the "comp" element.

    Returns:
        Character representing the channel orientation. One of 'N',
        'E', 'Z', 'H' (for horizontal), or 'U' (for unknown).
    """
    if not len(orig_channel.strip()):
        orientation = "U"  # default when we don't know anything about channel
        return orientation

    if orig_channel == "mmi" or orig_channel == "DERIVED":
        orientation = "H"  # mmi is arbitrarily horizontal
    elif orig_channel[-1] in ("N", "E", "Z"):
        orientation = orig_channel[-1]
    elif orig_channel == "UNK":  # Channel is "UNK"; assume horizontal
        orientation = "H"
    elif orig_channel == "H1" or orig_channel == "H2":
        orientation = "H"
    elif orig_channel[-1].isdigit():
        if orient == "h":
            orientation = "H"
        elif orient == "v":
            orientation = "Z"
        else:
            orientation = "U"
    else:
        orientation = "U"  # this is unknown

    return orientation


def _getOrientationSet(chan_names):
    """
    Return a characters representing the orientation of a set of
    channels from a single station.

    Args:
        chan_names (list):
            List of strings representing the seed channels (e.g. 'HNZ').
            The final character is assumed to be the (uppercase)
            orientation.

    Returns:
        Character representing the channel orientation. One of 'N',
        'E', 'Z', 'H' (for horizontal), or 'U' (for unknown).
    """
    if len(chan_names) == 3:
        term_chars = [chan_names[0][-1], chan_names[1][-1], chan_names[2][-1]]
        if "1" in term_chars and "Z" in term_chars:
            orientations = [(lambda x: "V" if x == "Z" else "H")(x) for x in term_chars]
            return orientations
    orientations = []
    for name in chan_names:
        orientations.append(_getOrientation(name, None))
    return orientations
