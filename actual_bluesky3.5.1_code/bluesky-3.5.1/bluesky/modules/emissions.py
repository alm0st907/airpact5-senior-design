"""bluesky.modules.emissions"""

__author__ = "Joel Dubowy"

import itertools
import logging

from emitcalc import __version__ as emitcalc_version
from emitcalc.calculator import EmissionsCalculator
from eflookup import __version__ as eflookup_version
from eflookup.fccs2ef.lookup import Fccs2Ef
from eflookup.fepsef import FepsEFLookup

import consume

from bluesky import datautils
from bluesky.exceptions import BlueSkyConfigurationError

from bluesky.consumeutils import (
    _apply_settings, FuelLoadingsManager, FuelConsumptionForEmissions, CONSUME_FIELDS
)

__all__ = [
    'run'
]
__version__ = "0.1.0"

TONS_PER_POUND = 0.0005 # 1.0 / 2000.0

def run(fires_manager):
    """Runs emissions module

    Args:
     - fires_manager -- bluesky.models.fires.FiresManager object

    Config options:
     - emissions > efs -- emissions factors model to use
     - emissions > species -- whitelist of species to compute emissions for
     - emissions > include_emissions_details -- whether or not to include
        emissions per fuel category per phase, as opposed to just per phase
     - emissions > fuel_loadings --
     - consumption > fuel_loadings -- considered if fuel loadings aren't
        specified emissions config
    """
    # TODO: rename 'efs' config field as 'model', since 'consume' isn't really
    #   just a different set of EFs - uisng 'model' is more general and
    #   appropriate given the three options. (maybe still support 'efs' as an alias)
    efs = fires_manager.get_config_value('emissions', 'efs', default='feps').lower()
    species = fires_manager.get_config_value('emissions', 'species', default=[])
    include_emissions_details = fires_manager.get_config_value('emissions',
        'include_emissions_details', default=False)
    fires_manager.processed(__name__, __version__, ef_set=efs,
        emitcalc_version=emitcalc_version, eflookup_version=eflookup_version)
    if efs == 'urbanski':
        _run_urbanski(fires_manager, species, include_emissions_details)
    elif efs == 'feps':
        _run_feps(fires_manager, species, include_emissions_details)
    elif efs == 'consume':
        _run_consume(fires_manager, species, include_emissions_details)
    else:
        raise BlueSkyConfigurationError(
            "Invalid emissions factors set: '{}'".format(efs))

    # fix keys
    for fire in fires_manager.fires:
        with fires_manager.fire_failure_handler(fire):
            for g in fire.growth:
                for fb in g['fuelbeds']:
                    _fix_keys(fb['emissions'])
                    if include_emissions_details:
                        _fix_keys(fb['emissions_details'])

    # For each fire, aggregate emissions over all fuelbeds per growth
    # window as well as across all growth windows;
    # include only per-phase totals, not per category > sub-category > phase
    for fire in fires_manager.fires:
        with fires_manager.fire_failure_handler(fire):
            # TODO: validate that each fuelbed has emissions data (here, or below) ?
            for g in fire.growth:
                g['emissions'] = datautils.summarize([g], 'emissions',
                    include_details=False)
            fire.emissions = datautils.summarize(fire.growth, 'emissions',
                include_details=False)

    # summarise over all growth objects
    all_growth = list(itertools.chain.from_iterable(
        [f.growth for f in fires_manager.fires]))
    summary = dict(emissions=datautils.summarize(all_growth, 'emissions'))
    if include_emissions_details:
        summary.update(emissions_details=datautils.summarize(
            all_growth, 'emissions_details'))
    fires_manager.summarize(**summary)

def _fix_keys(emissions):
    for k in emissions:
        # in case someone spcifies custom EF's with 'PM25'
        if k == 'PM25':
            emissions['PM2.5'] = emissions.pop('PM25')
        elif k == 'NMOC':
            # Total non-methane VOCs
            emissions['VOC'] = emissions.pop('NMOC')
        elif isinstance(emissions[k], dict):
            _fix_keys(emissions[k])

##
## FEPS
##

def _run_feps(fires_manager, species, include_emissions_details):
    logging.info("Running emissions module FEPS EFs")

    # The same lookup object is used for both Rx and WF
    calculator = EmissionsCalculator(FepsEFLookup(), species=species)
    for fire in fires_manager.fires:
        with fires_manager.fire_failure_handler(fire):
            if 'growth' not in fire:
                raise ValueError(
                    "Missing growth data required for computing emissions")
            for g in fire.growth:
                if 'fuelbeds' not in g:
                   raise ValueError(
                        "Missing fuelbed data required for computing emissions")
                for fb in g['fuelbeds']:
                    if 'consumption' not in fb:
                        raise ValueError(
                            "Missing consumption data required for computing emissions")
                    _calculate(calculator, fb, include_emissions_details)
                    # TODO: Figure out if we should indeed convert from lbs to tons;
                    #   if so, uncomment the following
                    # Note: According to BSF, FEPS emissions are in lbs/ton consumed.  Since
                    # consumption is in tons, and since we want emissions in tons, we need
                    # to divide each value by 2000.0
                    # datautils.multiply_nested_data(fb['emissions'], TONS_PER_POUND)
                    # if include_emissions_details:
                    #     datautils.multiply_nested_data(fb['emissions_details'], TONS_PER_POUND)

##
## Urbanski
##

def _run_urbanski(fires_manager, species, include_emissions_details):
    logging.info("Running emissions module with Urbanski EFs")

    # Instantiate two lookup object, one Rx and one WF, to be reused
    for fire in fires_manager.fires:
        with fires_manager.fire_failure_handler(fire):
            if 'growth' not in fire:
                raise ValueError(
                    "Missing growth data required for computing emissions")

            for g in fire.growth:
                if 'fuelbeds' not in g:
                    raise ValueError(
                        "Missing fuelbed data required for computing emissions")
                for fb in g['fuelbeds']:
                    if 'consumption' not in fb:
                        raise ValueError(
                            "Missing consumption data required for computing emissions")
                    fccs2ef = Fccs2Ef(fb["fccs_id"], is_rx=(fire.type=="rx"))
                    calculator = EmissionsCalculator(fccs2ef, species=species)
                    _calculate(calculator, fb, include_emissions_details)
                    # Convert from lbs to tons
                    # TODO: Update EFs to be tons/ton in a) eflookup package,
                    #   b) just after instantiating look-up objects, above,
                    #   or c) just before calling EmissionsCalculator, above
                    datautils.multiply_nested_data(fb['emissions'], TONS_PER_POUND)
                    if include_emissions_details:
                        datautils.multiply_nested_data(fb['emissions_details'], TONS_PER_POUND)

##
## CONSUME
##

def _run_consume(fires_manager, species, include_emissions_details):
    logging.info("Running emissions module with CONSUME")

    # look for custom fuel loadings first in the emissions config and then
    # in the consumption config
    all_fuel_loadings = fires_manager.get_config_value(
        'emissions','fuel_loadings')
    all_fuel_loadings = all_fuel_loadings or fires_manager.get_config_value(
        'consumption','fuel_loadings')
    fuel_loadings_manager = FuelLoadingsManager(
        all_fuel_loadings=all_fuel_loadings)
    if species:
        species = [e.upper() for e in species]

    for fire in fires_manager.fires:
        with fires_manager.fire_failure_handler(fire):
            _run_consume_on_fire(fuel_loadings_manager, species,
                include_emissions_details, fire)

def _run_consume_on_fire(fuel_loadings_manager, species,
        include_emissions_details, fire):
    logging.debug("Consume emissions - fire {}".format(fire.id))

    if 'growth' not in fire:
        raise ValueError(
            "Missing growth data required for computing emissions")

    # TODO: set burn type to 'activity' if fire.fuel_type == 'piles' ?
    if fire.fuel_type == 'piles':
        raise ValueError("Consume can't be used for fuel type 'piles'")
    burn_type = fire.fuel_type

    for g in fire.growth:
        if 'fuelbeds' not in g:
            raise ValueError(
                "Missing fuelbed data required for computing emissions")


        for fb in g['fuelbeds']:
            _run_consume_on_fuelbed(fuel_loadings_manager, species,
                include_emissions_details, fb, g['location'], burn_type)

def _run_consume_on_fuelbed(fuel_loadings_manager, species,
        include_emissions_details, fb, location, burn_type):
    if 'consumption' not in fb:
        raise ValueError(
            "Missing consumption data required for computing emissions")
    if 'heat' not in fb:
        raise ValueError(
            "Missing heat data required for computing emissions")

    fuel_loadings_csv_filename = fuel_loadings_manager.generate_custom_csv(
         fb['fccs_id'])
    area = (fb['pct'] / 100.0) * location['area']
    fc = FuelConsumptionForEmissions(fb["consumption"], fb['heat'],
        area, burn_type, fb['fccs_id'], location,
        fccs_file=fuel_loadings_csv_filename)

    fb['emissions_fuel_loadings'] = fuel_loadings_manager.get_fuel_loadings(fb['fccs_id'], fc.FCCS)
    e = consume.Emissions(fuel_consumption_object=fc)

    r = e.results()['emissions']
    fb['emissions'] = {f: {} for f in CONSUME_FIELDS}
    # r's key hierarchy is species > phase; we want phase > species
    for k in r:
        upper_k = 'PM2.5' if k == 'pm25' else k.upper()
        if k != 'stratum' and (not species or upper_k in species):
            for p in r[k]:
                fb['emissions'][p][upper_k] = r[k][p]
    if include_emissions_details:
        # Note: consume gives details per fuel category, not per
        #  subcategory; to match what feps and urbanski calculators
        #  produce, put all per-category details under'summary'
        # The details are under key 'stratum'. the key hierarchy is:
        #    'stratum' > species > fuel category > phase
        #   we want phase > species:
        #     'summary' > fuel category > phase > species
        fb['emissions_details'] = { "summary": {} }
        for k in r.get('stratum', {}):
            upper_k = 'PM2.5' if k == 'pm25' else k.upper()
            if not species or upper_k in species:
                for c in r['stratum'][k]:
                    fb['emissions_details']['summary'][c] = fb['emissions_details']['summary'].get(c, {})
                    for p in r['stratum'][k][c]:
                        fb['emissions_details']['summary'][c][p] = fb['emissions_details']['summary'][c].get(p, {})
                        fb['emissions_details']['summary'][c][p][upper_k] = r['stratum'][k][c][p]

    # Note: We don't need to call
    #   datautils.multiply_nested_data(fb["emissions"], area)
    # because the consumption and heat data set in fc were assumed to
    # have been multiplied by area.

    # TODO: act on 'include_emissions_details'?  consume emissions
    #   doesn't provide as detailed emissions as FEPS and Urbanski;
    #   it lists per-category emissions, not per-sub-category

##
## Helpers
##

def _calculate(calculator, fb, include_emissions_details):
    emissions_details = calculator.calculate(fb["consumption"])
    fb['emissions'] = emissions_details['summary']['total']
    if include_emissions_details:
        fb['emissions_details'] = emissions_details
