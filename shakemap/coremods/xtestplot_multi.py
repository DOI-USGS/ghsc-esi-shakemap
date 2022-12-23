# stdlib
import glob
import os.path

# third party
import matplotlib.pyplot as plt
from esi_utils_io.smcontainers import ShakeMapOutputContainer

# local imports
from shakelib.utils.imt_string import oq_to_file
from shakemap.coremods.base import CoreModule
from shakemap.utils.config import get_config_paths


class XTestPlotMulti(CoreModule):
    """
    xtestplot_multi -- Plot 1D sections of test events, combining multiple
    plots that have the same base eventid..
    """

    command_name = "xtestplot_multi"

    def execute(self):
        """
        Raises:
            NotADirectoryError: When the event data directory does not exist.
            FileNotFoundError: When the the shake_result HDF file does not
                exist.
        """
        install_path, data_path = get_config_paths()
        event_paths = glob.glob(os.path.join(data_path, f"{self._eventid}*"))
        datalist = []
        sigmas = []
        for path in event_paths:
            datadir = os.path.join(path, "current", "products")
            if not os.path.isdir(datadir):
                raise NotADirectoryError(f"{datadir} is not a valid directory.")
            datafile = os.path.join(datadir, "shake_result.hdf")
            if not os.path.isfile(datafile):
                raise FileNotFoundError(f"{datafile} does not exist.")

            # Open the ShakeMapOutputContainer and extract the data
            container = ShakeMapOutputContainer.load(datafile)
            if container.getDataType() != "points":
                raise NotImplementedError(
                    "xtestplot_multi module can only "
                    "operate on sets of points, not "
                    "gridded data"
                )

            stas = container.getStationDict()
            ampd = stas["features"][0]["properties"]["channels"][0]["amplitudes"][0]
            if "ln_sigma" in ampd:
                sigmas.append(ampd["ln_sigma"])
            else:
                sigmas.append(0)
            datadict = {}
            imtlist = container.getIMTs("GREATER_OF_TWO_HORIZONTAL")
            for myimt in imtlist:
                datadict[myimt] = container.getIMTArrays(
                    myimt, "GREATER_OF_TWO_HORIZONTAL"
                )
            datalist.append(datadict)

        container.close()
        #
        # Make plots
        #
        colors = ["k", "b", "g", "r", "c", "m"]
        for myimt in imtlist:
            fig, axa = plt.subplots(2, sharex=True, figsize=(10, 8))
            plt.subplots_adjust(hspace=0.1)
            for ix, dd in enumerate(datalist):
                data = dd[myimt]
                axa[0].plot(
                    data["lons"],
                    data["mean"],
                    color=colors[ix],
                    label=r"$\sigma_\epsilon = %.2f$" % sigmas[ix],
                )
                axa[1].plot(
                    data["lons"],
                    data["std"],
                    "-.",
                    color=colors[ix],
                    label=r"$\sigma_\epsilon = %.2f$" % sigmas[ix],
                )
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
            pfile = os.path.join(
                event_paths[0],
                "current",
                "products",
                self._eventid + "_" + fileimt + ".pdf",
            )
            plt.savefig(pfile)
            pfile = os.path.join(
                event_paths[0],
                "current",
                "products",
                self._eventid + "_" + fileimt + ".png",
            )
            plt.savefig(pfile)
            plt.close()
