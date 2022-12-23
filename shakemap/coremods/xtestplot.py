# stdlib
import os.path

# third party
import matplotlib.pyplot as plt
from esi_utils_io.smcontainers import ShakeMapOutputContainer

# local imports
from shakelib.utils.imt_string import oq_to_file
from shakemap.coremods.base import CoreModule
from shakemap.utils.config import get_config_paths


class XTestPlot(CoreModule):
    """
    xtestplot -- Plot 1D sections of test events.
    """

    command_name = "xtestplot"

    def execute(self):
        """
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
        container = ShakeMapOutputContainer.load(datafile)
        if container.getDataType() != "points":
            raise NotImplementedError(
                "xtestplot module can only operate on "
                "sets of points, not gridded data"
            )

        datadict = {}
        imtlist = container.getIMTs("GREATER_OF_TWO_HORIZONTAL")
        for myimt in imtlist:
            datadict[myimt] = container.getIMTArrays(myimt, "GREATER_OF_TWO_HORIZONTAL")
        container.close()

        #
        # Make plots
        #
        for myimt in imtlist:
            data = datadict[myimt]
            fig, axa = plt.subplots(2, sharex=True, figsize=(10, 8))
            plt.subplots_adjust(hspace=0.1)
            axa[0].plot(data["lons"], data["mean"], color="k", label="mean")
            axa[0].plot(
                data["lons"], data["mean"] + data["std"], "--b", label="mean +/- stddev"
            )
            axa[0].plot(data["lons"], data["mean"] - data["std"], "--b")
            axa[1].plot(data["lons"], data["std"], "-.r", label="stddev")
            plt.xlabel("Longitude")
            axa[0].set_ylabel(f"Mean ln({myimt}) (g)")
            axa[1].set_ylabel(f"Stddev ln({myimt}) (g)")
            axa[0].legend(loc="best")
            axa[1].legend(loc="best")
            axa[0].set_title(self._eventid)
            axa[0].grid()
            axa[1].grid()
            axa[1].set_ylim(bottom=0)
            fileimt = oq_to_file(myimt)
            pfile = os.path.join(datadir, self._eventid + "_" + fileimt + ".pdf")
            plt.savefig(pfile)
            pfile = os.path.join(datadir, self._eventid + "_" + fileimt + ".png")
            plt.savefig(pfile)
            plt.close()
