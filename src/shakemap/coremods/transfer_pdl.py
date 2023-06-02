# stdlib imports
import logging
import os.path
import shutil

# third party imports
from esi_utils_transfer.pdlsender import PDLSender

# local imports
from shakemap.coremods.transfer_base import TransferBaseModule


class PDLTransfer(TransferBaseModule):
    """
    transfer_pdl - Transfer content via PDL to a remote server.
    """

    command_name = "transfer_pdl"
    dependencies = [("products/*", False)]

    def __init__(self, eventid):
        # call the parent constructor
        super(PDLTransfer, self).__init__(eventid)

    def execute(self):
        # call parent execute() method
        # this will set the self.info and self.config
        # dictionaries, and self.datadir
        super(PDLTransfer, self).execute()

        # check to see if PDL is a configured method
        if "pdl" not in self.config:
            logging.info("No PDL transfer has been configured. Returning.")
            return

        # do PDL specific stuff

        pdl_dir = os.path.join(self.datadir, "pdl")
        products_dir = os.path.join(self.datadir, "products")
        if not os.path.isdir(pdl_dir):
            raise NotADirectoryError(f"{pdl_dir} does not exist.")

        # get the properties needed for the sender
        properties, product_properties = self.getProperties(self.info)

        downloads_dir = os.path.join(pdl_dir, "download")
        if os.path.isdir(downloads_dir):
            shutil.rmtree(downloads_dir, ignore_errors=True)
        shutil.copytree(products_dir, downloads_dir)

        # loop over all possible pdl destinations, send products to
        # each one
        for destination, params in self.config["pdl"].items():
            cmdline_args = {}
            if "cmdline_args" in params:
                cmdline_args = params["cmdline_args"].copy()
                del params["cmdline_args"]

            params.update(properties)

            if "properties" in params:
                product_properties.update(params["properties"])
                del params["properties"]

            if self.usedevconfig is True:
                if params["devconfig"] is None or not os.path.isfile(
                    params["devconfig"]
                ):
                    raise FileNotFoundError(
                        f"Dev config file \"{params['devconfig']}\" does not exist"
                    )
                # Swap the config file for the devconfig file
                params["configfile"] = params["devconfig"]
                fmt = f"Doing PDL transfer to {destination} DEV..."
                logging.debug(fmt)
            else:
                fmt = f"Doing PDL transfer to {destination}..."
                logging.debug(fmt)

            sender = PDLSender(
                properties=params,
                local_directory=pdl_dir,
                product_properties=product_properties,
                cmdline_args=cmdline_args,
            )
            logging.debug(f"Properties: {params}")
            logging.debug(f"Product Properties: {product_properties}")
            logging.debug(f"Cmdline Args: {cmdline_args}")
            if self.cancel:
                msg = sender.cancel()
            else:
                nfiles, msg = sender.send()
                fmt = '%i files sent.  Message from sender: \n"%s"'
                tpl = (nfiles, msg)
                logging.info(fmt % tpl)

        if not self.cancel:
            shutil.rmtree(downloads_dir, ignore_errors=True)
