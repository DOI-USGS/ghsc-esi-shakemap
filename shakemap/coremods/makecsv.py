# stdlib imports
import argparse
import inspect
import json
import os.path
import pathlib
import re

# third party imports
import h5py
import numpy as np
import pandas as pd

# local imports
from shakemap.coremods.base import CoreModule
from shakemap.utils.config import get_config_paths
from shakemap.utils.dataframe import generate_ids

STATS = ["mean", "std"]


def get_row_col(geodict, lat, lon):
    ulx = geodict["xmin"]
    uly = geodict["ymax"]
    dx = geodict["dx"]
    dy = geodict["dy"]
    # check to see if we're in a scenario where the grid crosses the meridian
    if geodict["xmax"] < ulx and lon < 0:
        lon += 360

    col = (lon - ulx) / dx
    row = (uly - lat) / dy
    col = np.round(col).astype(np.int32)
    row = np.round(row).astype(np.int32)
    newlon = ulx + col * dx
    newlat = uly - row * dy
    return (row, col, newlat, newlon)


def read_hdf_points(fileobj):
    imclist = fileobj["arrays"]["imts"].keys()
    arrays = fileobj["arrays"]["imts"][imclist[0]]
    val_columns = {}
    val_columns["id"] = [rowid.decode("utf8") for rowid in arrays["PGA"]["ids"][:]]
    val_columns["lat"] = arrays["PGA"]["lats"][:]
    val_columns["lon"] = arrays["PGA"]["lons"][:]
    dataframes = {}
    for imc in imclist:
        arrays = fileobj["arrays"]["imts"][imc]
        for imt, group in arrays.items():
            for stat, array in group.items():
                if stat in ["ids", "lats", "lons"]:
                    continue
                key = f"{imt}_{stat}"
                val_columns[key] = array[:]

        dataframe = pd.DataFrame(data=val_columns)
        dataframes[imc] = dataframe
    return dataframes


def read_hdf_grid(fileobj, lats=None, lons=None, ids=None):
    imclist = fileobj["arrays"]["imts"].keys()
    dataframes = {}
    val_columns = {}
    if lats is not None:
        val_columns["id"] = ids
        val_columns["lat"] = lats
        val_columns["lon"] = lons
    else:
        imc = list(fileobj["arrays"]["imts"].keys())[0]
        array = fileobj["arrays"]["imts"][imc]["PGA"]["mean"]
        gdict = dict(array.attrs)
        tlons = np.linspace(gdict["xmin"], gdict["xmax"], num=gdict["nx"])
        tlats = np.linspace(gdict["ymin"], gdict["ymax"], num=gdict["ny"])
        tlons, tlats = np.meshgrid(tlons, tlats)
        idvals = generate_ids(gdict["nx"] * gdict["ny"])
        tlons = tlons.flatten()
        tlats = tlats.flatten()
        val_columns["id"] = idvals
        val_columns["lat"] = tlats
        val_columns["lon"] = tlons
    for imc in imclist:
        for imt, group in fileobj["arrays"]["imts"][imc].items():
            for stat in STATS:
                array = group[stat]
                key = f"{imt}_{stat}"
                val_columns[key] = []
                if lats is None:
                    val_columns[key] = array[:].flatten()
                else:
                    nrows, ncols = array.shape
                    gdict = dict(array.attrs)
                    for lat, lon in zip(lats, lons):
                        row, col, newlat, newlon = get_row_col(gdict, lat, lon)
                        if row > nrows - 1 or col > ncols - 1 or row < 0 or col < 0:
                            value = np.nan
                        else:
                            value = array[row, col]
                        val_columns[key].append(value)

        dataframe = pd.DataFrame(data=val_columns)
        dataframes[imc] = dataframe
    return dataframes


class MakeCSVModule(CoreModule):
    """
    makecsv -- Make CSV files grid or points arrays found in results HDF file.
    """

    command_name = "makecsv"
    targets = []
    dependencies = [("products/shake_result.hdf", True)]

    def __init__(self, eventid):
        super(MakeCSVModule, self).__init__(eventid)
        self.sample_file = None
        self.eventid = eventid

    def execute(self):
        """
        Write info.json metadata file.

        Raises:
            NotADirectoryError: When the event data directory does not exist.
            FileNotFoundError: When the the shake_result HDF file does not
                exist.
        """
        install_path, data_path = get_config_paths()
        datadir = os.path.join(data_path, self._eventid, "current", "products")
        if not os.path.isdir(datadir):
            raise NotADirectoryError(f"{datadir} is not a valid directory.")
        datafile = os.path.join(datadir, "shake_result.hdf")
        if not os.path.isfile(datafile):
            raise FileNotFoundError(f"{datafile} does not exist.")

        # Open the ShakeMapOutputContainer and extract the data
        with h5py.File(datafile) as fobj:
            info = json.loads(fobj["dictionaries"]["info.json"][()])
            # detect points mode
            imc = list(fobj["arrays"]["imts"].keys())[0]
            pga = fobj["arrays"]["imts"][imc]["PGA"]
            points_mode = "lats" in pga
            mode = "grid"
            if points_mode:
                mode = "points"
                dataframes = read_hdf_points(fobj)
            else:
                lats = None
                lons = None
                ids = None
                if self.sample_file is not None:
                    lats, lons, ids = read_sampling_file(self.sample_file)
                dataframes = read_hdf_grid(fobj, lats=lats, lons=lons, ids=ids)
        # write out dataframe using model command line arguments and grid/points mode
        for imc, dataframe in dataframes.items():
            datadir = pathlib.Path(datadir)
            # figure out the filename
            fname = f"{self.eventid}_{mode}"
            for flag, value in info["processing"]["model_flags"].items():
                if value:
                    fname += f'_{flag.replace("_","")}'
            filename = (datadir / fname).with_suffix(".csv")
            dataframe.to_csv(filename, index=False)

    def parseArgs(self, arglist):
        """
        Set up the object to accept the --comment flag.
        """
        parser = argparse.ArgumentParser(
            prog=self.__class__.command_name, description=inspect.getdoc(self.__class__)
        )
        msg = (
            "For ShakeMaps created in grid mode, "
            "use this CSV/Excel file to extract using nearest neighbor "
            "the values at the input points."
            "The input file should "
            "be an Excel spreadsheet or CSV file with column headers:"
            " - lat (or any string beginning with 'lat' when lowercased) REQUIRED"
            " - lon (or any string beginning with 'lon' when lowercased) REQUIRED"
        )
        parser.add_argument("-s", "--sample-file", help=msg, default=None)
        #
        # This line should be in any modules that overrides this
        # one. It will collect up everything after the current
        # modules options in args.rem, which should be returned
        # by this function. Note: doing parser.parse_known_args()
        # will not work as it will suck up any later modules'
        # options that are the same as this one's.
        #
        parser.add_argument("rem", nargs=argparse.REMAINDER, help=argparse.SUPPRESS)
        args = parser.parse_args(arglist)
        self.sample_file = args.sample_file
        return args.rem


def read_sampling_file(filename):
    filename = pathlib.Path(filename)
    if filename.suffix == ".xlsx":
        dataframe = pd.read_excel(filename)
    else:
        dataframe = pd.read_csv(filename)
    """Modify a points dataframe for the assemble core module."""
    columns = list(dataframe.columns)
    regex_lat = re.compile("lat", re.IGNORECASE)
    regex_lon = re.compile("lon", re.IGNORECASE)
    regex_id = re.compile("id", re.IGNORECASE)
    latcols = list(filter(regex_lat.match, columns))
    loncols = list(filter(regex_lon.match, columns))
    idcols = list(filter(regex_id.match, columns))
    if not len(latcols) or not len(loncols):
        msg = "Missing lat/lon columns in input points " f"file with columns: {columns}"
        raise Exception(msg)

    if len(idcols):
        idvals = dataframe[idcols[0]]
    else:
        idvals = generate_ids(len(dataframe))

    # extract lats, lons, ids
    latcol = latcols[0]
    loncol = loncols[0]
    lats = dataframe[latcol].to_numpy()
    lons = dataframe[loncol].to_numpy()
    return (lats, lons, idvals)
