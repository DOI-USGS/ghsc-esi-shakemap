# stdlib imports
import os.path

# third party imports
import h5py
import pandas as pd

# local imports
from shakemap.coremods.base import Contents, CoreModule
from shakemap.utils.config import get_config_paths


class PointCSVModule(CoreModule):
    """
    info -- Extract point data from shake_result.hdf and write as CSV file.
    """

    command_name = "pointcsv"
    targets = [r"products/points\.csv"]
    dependencies = [("products/shake_result.hdf", True)]

    def __init__(self, eventid):
        super(PointCSVModule, self).__init__(eventid)
        self.contents = Contents(None, None, eventid)

    def execute(self):
        """
        Write points.csv data file from a "points" run of ShakeMap.

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
        fileobj = h5py.File(datafile, "r")
        rows = {}
        arrays = fileobj["arrays"]["imts"]["GREATER_OF_TWO_HORIZONTAL"]
        ids = list(arrays["MMI"]["ids"][()])
        ids = [id.decode("utf8") for id in ids]
        rows["id"] = ids
        rows["lat"] = arrays["MMI"]["lats"][()]
        rows["lon"] = arrays["MMI"]["lons"][()]

        for imt, array in arrays.items():
            mean_column = array["mean"][()]
            std_column = array["std"][()]
            mean_col = f"{imt}_mean"
            std_col = f"{imt}_std"
            rows[mean_col] = mean_column
            rows[std_col] = std_column

        dataframe = pd.DataFrame(rows)
        outfile = os.path.join(datadir, "points.csv")
        dataframe.to_csv(outfile, index=False)

        cap = "ShakeMap points results in CSV format."
        self.contents.addFile(
            "supplementalInformation",
            "Supplemental Information",
            cap,
            "points.csv",
            "application/text",
        )
