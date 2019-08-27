"""bluesky.modules.dispersion

If running hysplit dispersion, you'll need to obtain hysplit and various other
Executables. See the repo README.md for more information.
"""

__author__ = "Joel Dubowy"

import consume
import copy
import datetime
import importlib
import logging

from bluesky import datetimeutils
from bluesky.exceptions import BlueSkyConfigurationError
from bluesky.dispersers.hysplit import hysplit
from bluesky.datetimeutils import parse_datetime
from bluesky.io import create_dir_or_handle_existing

__all__ = [
    'run'
]

__version__ = "0.1.0"

def run(fires_manager):
    """Runs dispersion module

    Args:
     - fires_manager -- bluesky.models.fires.FiresManager object
    """
    model = fires_manager.get_config_value('dispersion', 'model',
        default='hysplit').lower()
    processed_kwargs = {}
    try:
        module, klass = _get_module_and_class(model)
        model_config = fires_manager.get_config_value(
            'dispersion', model, default={})

        start, num_hours = _get_time(fires_manager)
        met = _filter_met(fires_manager.met, start, num_hours)

        disperser = klass(met, **model_config)
        processed_kwargs.update({
            "{}_version".format(model): module.__version__
        })

        output_dir, working_dir = _get_dirs(fires_manager)

        # further validation of start and num_hours done in 'run'
        dispersion_info = disperser.run(fires_manager.fires, start,
            num_hours, output_dir, working_dir=working_dir)
        dispersion_info.update(model=model)
        # TODO: store dispersion into in summary?
        #   > fires_manager.summarize(disperion=disperser.run(...))
        fires_manager.dispersion = dispersion_info

        # TODO: add information about fires to processed_kwargs

    finally:
        fires_manager.processed(__name__, __version__, model=model,
            **processed_kwargs)

    # TODO: add information to fires_manager indicating where to find the hysplit output

def _filter_met(met, start, num_hours):
    # the passed-in met is a reference to the fires_manager's met, so copy it
    met = copy.deepcopy(met)

    if not met:
        # return `met` in case it's a dict and dict is expected downstream
        return met

    # limit met to only what's needed to cover dispersion window
    end = start + datetime.timedelta(hours=num_hours)

    # Note: we don't store the parsed first and last hour values
    # because they aren't used outside of this method, and they'd
    # just have to be dumped back to string values when bsp exits
    logging.debug('Determinig met files needed for dispersion')
    met_files = met.pop('files', [])
    met["files"] = []
    for m in met_files:
        if (parse_datetime(m['first_hour']) <= end
                and parse_datetime(m['last_hour']) >= start):
            met["files"].append(m)
        else:
            logging.debug('Dropping met file %s - not needed for dispersion',
                m["file"])
    return met

def _get_module_and_class(model):
    module_name = "bluesky.dispersers.{}".format(model)
    logging.debug("Importing %s", module_name)
    try:
        module = importlib.import_module(module_name)
    except ImportError:
        raise BlueSkyConfigurationError(
            "Invalid dispersion model: '{}'".format(model))

    klass_name = "{}Dispersion".format(model.upper())
    logging.debug("Loading class %s", klass_name)
    try:
        klass = getattr(module, klass_name)
    except:
        # TODO: use more appropriate exception class
        raise RuntimeError("{} does not define class {}".format(
            module_name, klass_name))

    return module, klass

SECONDS_PER_HOUR = 3600

def _get_time(fires_manager):
    start = fires_manager.get_config_value('dispersion', 'start')
    num_hours = fires_manager.get_config_value('dispersion', 'num_hours')

    if not start or num_hours is None:
        s = fires_manager.earliest_start # needed for 'start' and 'num_hours'
        if not s:
            raise ValueError("Unable to determine dispersion 'start'")
        if not start:
            start = s

        if not num_hours and start == s:
            e = fires_manager.latest_end # needed only for num_hours
            if e and e > s:
                num_hours = int((e - s).total_seconds() / SECONDS_PER_HOUR)
        if not num_hours:
            raise ValueError("Unable to determine dispersion 'num_hours'")

    logging.debug("Dispersion window: %s for %s hours", start, num_hours)
    return start, num_hours


def _get_dirs(fires_manager):
    handle_existing = fires_manager.get_config_value('dispersion',
        'handle_existing', default='fail')

    output_dir = fires_manager.get_config_value('dispersion', 'output_dir')
    if not output_dir:
        raise ValueError("Specify dispersion output directory")
    create_dir_or_handle_existing(output_dir, handle_existing)

    working_dir = fires_manager.get_config_value('dispersion', 'working_dir')
    if working_dir:
        create_dir_or_handle_existing(working_dir, handle_existing)

    return output_dir, working_dir
