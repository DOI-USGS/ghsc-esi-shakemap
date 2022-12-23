# local imports
from shakemap.coremods.transfer_base import TransferBaseModule


class SaveTransfer(TransferBaseModule):
    """
    save - Create backup directory and prep for next ShakeMap map version.
    """

    command_name = "save"
    dependencies = [("products/*", False)]

    def __init__(self, eventid):
        # call the parent constructor
        super(SaveTransfer, self).__init__(eventid)

    def execute(self):
        # Calling parent class execute method, which serves to
        # perform backup functionality for us.
        super(SaveTransfer, self).execute()
