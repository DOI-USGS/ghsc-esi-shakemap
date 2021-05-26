# stdlib imports
import os.path
import glob
import json
import shutil

# third party imports
import fiona
from fiona.crs import from_epsg
from openquake.hazardlib import imt
from configobj import ConfigObj

# local imports
from .base import CoreModule, Contents
from shakelib.plotting.contour import contour
from shakemap.utils.utils import get_object_from_config
from impactutils.io.smcontainers import ShakeMapOutputContainer
from shakelib.utils.imt_string import oq_to_file
from shakemap.utils.config import (get_config_paths,
                                   get_configspec,
                                   get_custom_validator,
                                   config_error)

FORMATS = {
    'geojson': ('GeoJSON', 'json')
}

DEFAULT_FILTER_SIZE = 10


class ContourModule(CoreModule):
    """
    contour -- Generate contours of all IMT values from the
                     shake_result.hdf output file.
    """

    command_name = 'contour'
    targets = [r'products/cont_.*\.json']
    dependencies = [('products/shake_result.hdf', True)]

    def __init__(self, eventid, filter=None):
        super(ContourModule, self).__init__(eventid)

        if filter is not None:
            self.filter_size = filter
        else:
            self.filter_size = DEFAULT_FILTER_SIZE

        self.contents = Contents("Ground Motion Contours", "contours", eventid)

    def execute(self):
        """
        Create contour files for all configured IMT values.

        Raises:
            NotADirectoryError: When the event data directory does not exist.
            FileNotFoundError: When the the shake_result HDF file does not
                exist.
        """
        install_path, data_path = get_config_paths()
        datadir = os.path.join(data_path, self._eventid, 'current', 'products')
        if not os.path.isdir(datadir):
            raise NotADirectoryError('%s is not a valid directory.' % datadir)
        datafile = os.path.join(datadir, 'shake_result.hdf')
        if not os.path.isfile(datafile):
            raise FileNotFoundError('%s does not exist.' % datafile)

        # Open the ShakeMapOutputContainer and extract the data
        container = ShakeMapOutputContainer.load(datafile)

        # get the path to the products.conf file, load the config
        config_file = os.path.join(install_path, 'config', 'products.conf')
        spec_file = get_configspec('products')
        validator = get_custom_validator()
        config = ConfigObj(config_file, configspec=spec_file)
        results = config.validate(validator)
        if not isinstance(results, bool) or not results:
            config_error(config, results)

        if container.getDataType() != 'grid':
            raise NotImplementedError('contour module can only contour '
                                      'gridded data, not sets of points')

        # get the filter size from the products.conf
        filter_size = config['products']['contour']['filter_size']

        # create contour files
        self.logger.debug('Contouring to files...')
        contour_to_files(container, datadir, self.logger, self.contents,
                         filter_size)
        container.close()


def contour_to_files(container, output_dir, logger, contents,
                     filter_size=DEFAULT_FILTER_SIZE):
    """
    Generate contours of all IMT values.

    Args:
      container (ShakeMapOutputContainer): ShakeMapOutputContainer with
          ShakeMap output data.
      output_dir (str): Path to directory where output files will be written.
      logger (logging.Logger): Python logging Logger instance.

    Raises:
        LookupError: When configured file format is not supported
    """

    # Right now geojson is all we support; if that changes, we'll have
    # to add a configuration or command-line option
    file_format = 'geojson'
    # open a file for writing
    driver, extension = FORMATS[file_format]
    sa_schema = {
        'geometry': 'MultiLineString',
        'properties': {
            'value': 'float',
            'units': 'str',
            'color': 'str',
            'weight': 'int'
        }
    }
    mmi_schema = {
        'geometry': 'MultiLineString',
        'properties': {
            'value': 'float',
            'units': 'str',
            'color': 'str',
            'weight': 'int'
        }
    }
    crs = from_epsg(4326)

    config = container.getConfig()
    gmice = get_object_from_config('gmice', 'modeling', config)
    gmice_imts = gmice.DEFINED_FOR_INTENSITY_MEASURE_TYPES
    gmice_pers = gmice.DEFINED_FOR_SA_PERIODS

    imtlist = container.getIMTs()
    for imtype in imtlist:
        component, imtype = imtype.split('/')
        fileimt = oq_to_file(imtype)
        oqimt = imt.from_string(imtype)
        if component == 'GREATER_OF_TWO_HORIZONTAL':
            fname = 'cont_%s.%s' % (fileimt, extension)
        else:
            fname = 'cont_%s_%s.%s' % (fileimt, component, extension)
        if imtype == 'MMI':
            contents.addFile('mmiContour', 'Intensity Contours',
                             'Contours of macroseismic intensity.',
                             fname, 'application/json')
            contents.addFile('miContour', 'Intensity Contours (Legacy Naming)',
                             'Contours of macroseismic intensity.',
                             'cont_mi.json', 'application/json')
        elif imtype == 'PGA':
            contents.addFile('pgaContour', 'PGA Contours',
                             'Contours of ' + component + ' peak '
                             'ground acceleration (%g).',
                             fname, 'application/json')
        elif imtype == 'PGV':
            contents.addFile('pgvContour', 'PGV Contours',
                             'Contours of ' + component + ' peak '
                             'ground velocity (cm/s).',
                             fname, 'application/json')
        else:
            contents.addFile(imtype + 'Contour',
                             imtype.upper() + ' Contours',
                             'Contours of ' + component + ' 5% damped ' +
                             str(oqimt.period) +
                             ' sec spectral acceleration (%g).',
                             fname, 'application/json')

        filename = os.path.join(output_dir, fname)
        if os.path.isfile(filename):
            fpath, fext = os.path.splitext(filename)
            flist = glob.glob(fpath + '.*')
            for fname in flist:
                os.remove(fname)

        if imtype == 'MMI' or not isinstance(oqimt, tuple(gmice_imts)) or \
           (isinstance(oqimt, imt.SA) and oqimt.period not in gmice_pers):
            my_gmice = None
        else:
            my_gmice = gmice

        # fiona spews a warning here when driver is geojson
        # this warning appears to be un-catchable using
        # with warnings.catch_warnings()
        # or
        # logging.captureWarning()
        # or
        # even redirecting stderr/stdout to IO streams
        # not sure where the warning is coming from,
        # but there appears to be no way to stop it...
        with fiona.Env():
            if imtype == 'MMI':
                selected_schema = mmi_schema
            else:
                selected_schema = sa_schema
            vector_file = fiona.open(
                filename, 'w',
                driver=driver,
                schema=selected_schema,
                crs=crs
            )

            line_strings = contour(container.getIMTGrids(imtype, component),
                                   imtype, filter_size, my_gmice)

            for feature in line_strings:
                vector_file.write(feature)

                # Grab some metadata
            meta = container.getMetadata()
            event_info = meta['input']['event_information']
            mdict = {
                'eventid': event_info['event_id'],
                'longitude': float(event_info['longitude']),
                'latitude': float(event_info['latitude'])
            }

            logger.debug('Writing contour file %s' % filename)
            vector_file.close()

            # Get bounds
            tmp = fiona.open(filename)
            bounds = tmp.bounds
            tmp.close()

            # Read back in to add metadata/bounds
            data = json.load(open(filename))
            data['metadata'] = mdict
            data['bbox'] = bounds
            with open(filename, 'w') as outfile:
                json.dump(data, outfile)

            #####################################
            # Make an extra version of the MMI contour file
            # so that the current web rendering code can find it.
            # Delete this file once everyone has moved to new version
            # of ComCat code.

            if imtype == 'MMI':
                old_file = os.path.join(output_dir, 'cont_mi.json')
                shutil.copy(filename, old_file)
            #####################################
