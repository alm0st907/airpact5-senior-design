"""bluesky.visualizers.disersion"""

__author__ = "Joel Dubowy"

__all__ = [
    'HysplitVisualizer'
]
__version__ = "0.1.0"

import copy
import csv
import datetime
import json
import logging
import os
from collections import namedtuple

import afconfig
from pyairfire import osutils
from afdatetime import parsing as datetime_parsing

from blueskykml import (
    makedispersionkml, configuration as blueskykml_configuration,
    smokedispersionkml, __version__ as blueskykml_version
)

from bluesky.exceptions import BlueSkyConfigurationError
from bluesky.extrafilewriters.firescsvs import FiresCsvsWriter

###
### HYSPLIT Dispersion Visualization
###

ARGS = [
    "output_directory", "configfile",
    "prettykml", "verbose", "config_options",
    "inputfile","fire_locations_csv",
    "fire_events_csv", "smoke_dispersion_kmz_file",
    "fire_kmz_file","layers"
]
BlueskyKmlArgs = namedtuple('BlueskyKmlArgs', ARGS)

DEFAULT_FILENAMES = {
    "fire_locations_csv": 'fire_locations.csv',
    "fire_events_csv": 'fire_events.csv',
    "smoke_dispersion_kmz": 'smoke_dispersion.kmz',
    "fire_kmz": 'fire_locations.kmz'
}


##
## Visualizer class
##

class HysplitVisualizer(object):
    def __init__(self, fires_manager):
        self._hysplit_output_info = fires_manager.dispersion['output']
        self._fires = fires_manager.fires
        self._run_id = fires_manager.run_id
        self._config = fires_manager.get_config_value(
            'visualization', 'hysplit', default={})
        self._fires_manager = fires_manager

    def run(self):
        hysplit_output_directory = self._hysplit_output_info.get('directory')
        if not hysplit_output_directory:
            raise ValueError("hysplit output directory must be defined")
        if not os.path.isdir(hysplit_output_directory):
            raise RuntimeError("hysplit output directory {} is not valid".format(
                hysplit_output_directory))

        hysplit_output_file = self._hysplit_output_info.get('grid_filename')
        if not hysplit_output_file:
            raise ValueError("hysplit output file must be defined")
        hysplit_output_file = os.path.join(hysplit_output_directory, hysplit_output_file)
        if not os.path.isfile(hysplit_output_file):
            raise RuntimeError("hysplit output file {} does not exist".format(
                hysplit_output_file))

        if self._config.get('output_dir'):
            output_directory = self._config['output_dir']
        else:
            output_directory =  hysplit_output_directory
        data_dir = os.path.join(output_directory, self._config.get('data_dir') or '')
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)

        files = {
            'fire_locations_csv': self._get_file_name(
                data_dir, 'fire_locations_csv'),
            'fire_events_csv': self._get_file_name(
                data_dir, 'fire_events_csv'),
            'smoke_dispersion_kmz': self._get_file_name(
                output_directory, 'smoke_dispersion_kmz'),
            'fire_kmz': self._get_file_name(
                output_directory, 'fire_kmz')
        }

        self._generate_fire_csv_files(files['fire_locations_csv']['pathname'],
            files['fire_events_csv']['pathname'])

        self._generate_summary_json(output_directory)

        config_options = self._get_config_options(output_directory)

        layers = self._config.get('layers')
        args = BlueskyKmlArgs(
            output_directory=str(output_directory),
            configfile=None, # TODO: allow this to be configurable?
            prettykml=self._config.get('prettykml'),
            # in blueskykml, if verbose is True, then logging level will be set
            # DEBUG; otherwise, logging level is left as is.  bsp already takes
            # care of setting log level, so setting verbose to False will let
            # blueskykml inherit logging level
            verbose=False,
            config_options=config_options,
            inputfile=str(hysplit_output_file),
            fire_locations_csv=str(files['fire_locations_csv']['pathname']),
            fire_events_csv=str(files['fire_events_csv']['pathname']),
            smoke_dispersion_kmz_file=str(files['smoke_dispersion_kmz']['pathname']),
            fire_kmz_file=str(files['fire_kmz']['pathname']),
            # blueskykml now supports layers specified as list of ints
            layers=layers
        )

        try:
            # Note: using create_working_dir effectively marks any
            #  intermediate outputs for cleanup
            with osutils.create_working_dir() as wdir:
                makedispersionkml.main(args)
        except blueskykml_configuration.ConfigurationError as e:
            raise BlueSkyConfigurationError(".....")

        return {
            'blueskykml_version': blueskykml_version,
            "output": {
                "directory": output_directory,
                "hysplit_output_file": hysplit_output_file,
                "smoke_dispersion_kmz_filename": files['smoke_dispersion_kmz']['name'],
                "fire_kmz_filename": files['fire_kmz']['name'],
                "fire_locations_csv_filename": files['fire_locations_csv']['name'],
                "fire_events_csv_filename": files['fire_events_csv']['name']
                # TODO: add location of image files, etc.
            }
        }

    def _get_file_name(self, directory, f):
        name = self._config.get('{}_filename'.format(f), DEFAULT_FILENAMES[f])
        return {
            "name": name,
            "pathname": os.path.join(directory, name)
        }


    def _generate_fire_csv_files(self, fire_locations_csv_pathname,
            fire_events_csv_pathname):
        """Generates fire locations and events csvs

        These are used by blueskykml, but are also used by end users.
        If it weren't for end users wanting the files, we might want to
        consider refactoring blueskykml to accept the fire data in
        memory (in the call to makedispersionkml.main(args)) rather
        reading it from file.
        """
        # TODO: Make sure that the files don't already exists
        # TODO: look in blueskykml code to see what it uses from the two csvs

        # Note: the two pathnames will always be in the same dir
        dest_dir = os.path.dirname(fire_locations_csv_pathname)
        firescsvs_config = {
            'fire_locations_filename': os.path.basename(
                fire_locations_csv_pathname),
            'fire_events_filename': os.path.basename(
                fire_events_csv_pathname),
        }
        FiresCsvsWriter(dest_dir, **firescsvs_config).write(
            self._fires_manager)

    def _generate_summary_json(self, output_directory):
        """Creates summary.json (like BSF's) if configured to do so
        """
        if self._config.get('create_summary_json'):
            grid_params = self._hysplit_output_info.get("grid_parameters", {})
            d_from = d_to = None
            try:
                d_from = datetime_parsing.parse(
                    self._hysplit_output_info.get("start_time"))
                d_to = d_from + datetime.timedelta(
                    hours=self._hysplit_output_info.get("num_hours"))
            except:
                pass

            contents = {
                 "output_version": "2.0.0",
                 # TODO: populate with real values
                 "dispersion_period": {
                    "from": d_from and d_from.strftime("%Y%m%d %HZ"),
                    "to": d_to and d_to.strftime("%Y%m%d %HZ")
                },
                 "width_longitude": grid_params.get("width_longitude"),
                 "height_latitude": grid_params.get("height_latitude"),
                 "center_latitude": grid_params.get("center_latitude"),
                 "center_longitude":  grid_params.get("center_longitude"),
                 "model_configuration": "HYSPLIT"
            }

            contents_json = json.dumps(contents)
            logging.debug("generating summary.json: %s", contents_json)
            with open(os.path.join(output_directory, 'summary.json'), 'w') as f:
                f.write(contents_json)

    DEFAULT_FIRE_EVENT_ICON = "http://maps.google.com/mapfiles/ms/micons/firedept.png"
    def _get_config_options(self, output_directory):
        """Creates config options dict to be pass into BlueSkyKml

        This method supports specifying old BSF / blueskykml ini settings
        under the blueskykml_config config key, which (if defined) is expected
        to contain nested dicts (each dict representing a config section).
        e.g.

            "visualization": {
                "target": "dispersion",
                "hysplit": {
                    "output_dir": "/sdf/sdf/",
                    ...,
                    "blueskykml_config": {
                        "SmokeDispersionKMLInput": {
                            "FIRE_EVENT_ICON"  : "http://maps.google.com/mapfiles/ms/micons/firedept.png"
                        }
                        ...
                    }
                }
            }

         The config_options dict returned by this method is initialized with
         whatever is specified under blueskykml_config.  Then, specific
         config options are set if not already defined.

          - 'SmokeDispersionKMLInput' > 'FIRE_EVENT_ICON' -- set to
            "http://maps.google.com/mapfiles/ms/micons/firedept.png"
          - 'DispersionGridOutput' > 'OUTPUT_DIR'
        """
        config_options = copy.deepcopy(self._config.get('blueskykml_config') or {})

        # TODO: should we be using google's icon as the default?
        # Use google's fire icon instead of BlueSkyKml's built-in icon
        # (if an alternative isn't already specified)
        if afconfig.get_config_value(config_options,
                'SmokeDispersionKMLInput', 'FIRE_EVENT_ICON') is None:
            afconfig.set_config_value(config_options,
                self.DEFAULT_FIRE_EVENT_ICON,
                'SmokeDispersionKMLInput', 'FIRE_EVENT_ICON')

        # set output directory if not already specified
        if afconfig.get_config_value(config_options,
                'DispersionGridOutput', 'OUTPUT_DIR') is None:
            images_dir = str(os.path.join(output_directory,
                self._config.get('images_dir') or ''))
            afconfig.set_config_value(config_options, images_dir,
                'DispersionGridOutput', 'OUTPUT_DIR')

        return config_options
