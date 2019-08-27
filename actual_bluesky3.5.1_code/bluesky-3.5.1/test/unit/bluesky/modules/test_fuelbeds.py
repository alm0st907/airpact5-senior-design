"""Unit tests for bluesky.modules.fuelbeds"""

__author__ = "Joel Dubowy"

import copy
from unittest import mock

from py.test import raises

from bluesky.models.fires import Fire
from bluesky.modules import fuelbeds

GEOJSON = {
    "type": "MultiPolygon",
    "coordinates": [
        [
            [
                [-84.8194, 30.5222],
                [-84.8197, 30.5209],
                # ...add more coordinates...
                [-84.8193, 30.5235],
                [-84.8194, 30.5222]
            ]
        ]
    ]
}

## Valid fuelbed info

FUELBED_INFO_60_40 = {
    "fuelbeds": {
        "46": {
            "grid_cells": 6, "percent": 60.0
        },
        "47": {
            "grid_cells": 4, "percent": 40.0
        }
    },
    "units": "m^2",
    "grid_cells": 5,
    "area": 4617927.854331356
}

FUELBED_INFO_40_30_26_6 = {
    "fuelbeds": {
        "46": {
            "grid_cells": 8, "percent": 40.0
        },
        "47": {
            "grid_cells": 6, "percent": 30.0
        },
        "48": {
            "grid_cells": 5, "percent": 26.0
        },
        "49": {
            "grid_cells": 1, "percent": 4.0
        }
    },
    "units": "m^2",
    "grid_cells": 5,
    "area": 4617927.854331356
}

## Invalid fuelbed info

# total % < 100
FUELBED_INFO_60_30 = copy.deepcopy(FUELBED_INFO_60_40)
FUELBED_INFO_60_30['fuelbeds']['47']['percent'] = 30
# total % > 100
FUELBED_INFO_60_40_10 = copy.deepcopy(FUELBED_INFO_60_40)
FUELBED_INFO_60_40_10['fuelbeds']['50'] = {"grid_cells": 1, "percent": 10.0}


##
## Tests for summarize
##

class TestSummarize(object):

    def test_no_fires(self):
        assert fuelbeds.summarize([]) == []

    def test_one_fire(self):
        fires = [
            Fire({
                'growth':[{
                    "location":{"area": 10},
                    "fuelbeds":[
                        {"fccs_id": "1", "pct": 40},
                        {"fccs_id": "2", "pct": 60}
                    ]
                }]
            })
        ]
        summary = fuelbeds.summarize(fires)
        assert summary == fires[0]['growth'][0]['fuelbeds']

    def test_two_fires(self):
        fires = [
            Fire({
                'growth':[{
                    "location":{"area": 10},
                    "fuelbeds":[
                        {"fccs_id": "1", "pct": 30},
                        {"fccs_id": "2", "pct": 70}
                    ]
                }]
            }),
            Fire({
                'growth':[{
                    "location":{"area": 5},
                    "fuelbeds":[
                        {"fccs_id": "2", "pct": 10},
                        {"fccs_id": "3", "pct": 90}
                    ]
                }]
            })
        ]
        expected_summary = [
            {"fccs_id": "1", "pct": 20},
            {"fccs_id": "2", "pct": 50},
            {"fccs_id": "3", "pct": 30}
        ]
        summary = fuelbeds.summarize(fires)
        assert summary == expected_summary

    # TODO: def test_two_fires_two_growth_each(self):
##
## Tests for Estimator.estimate
##

class TestEstimatorInsufficientDataForLookup(object):

    def setup(self):
        lookup = mock.Mock()
        self.estimator = fuelbeds.Estimator(lookup)

    def test_no_growth(self):
        with raises(ValueError) as e:
            self.estimator.estimate({})

    def test_no_location(self):
        with raises(ValueError) as e:
            self.estimator.estimate({'growth':[{}]})

    def test_no_geojson_or_lat_or_lng(self):
        with raises(ValueError) as e:
            self.estimator.estimate({"growth":[{"location":{}}]})

class BaseTestEstimatorEstimate(object):
    """Base class for testing Estimator.estimate
    """

    def setup(self):
        lookup = mock.Mock()
        self.estimator = fuelbeds.Estimator(lookup)

    # Tests of invalid lookup data

    def test_none_lookup_info(self):
        self.estimator.lookup.look_up = lambda p: None
        with raises(RuntimeError) as e:
            self.estimator.estimate(self.growth_obj)

    def test_empty_lookup_info(self):
        self.estimator.lookup.look_up = lambda p: {}
        with raises(RuntimeError) as e:
            self.estimator.estimate(self.growth_obj)

    def test_lookup_info_percentages_less_than_100(self):
        self.estimator.lookup.look_up = lambda p: FUELBED_INFO_60_30
        with raises(RuntimeError) as e:
            self.estimator.estimate(self.growth_obj)

    def test_lookup_info_percentages_greater_than_100(self):
        self.estimator.lookup.look_up = lambda p: FUELBED_INFO_60_40_10
        with raises(RuntimeError) as e:
            self.estimator.estimate(self.growth_obj)

    # Test of valid lookup data

    def test_no_truncation(self):
        self.estimator.lookup.look_up = lambda p: FUELBED_INFO_60_40
        expected_fuelbeds = [
            {'fccs_id': '46', 'pct': 60},
            {'fccs_id': '47', 'pct': 40}
        ]
        # Having 'geojson' key will trigger call to self.estimator.lookup.look_up;
        # The value of GeoJSON is not actually used here
        self.estimator.estimate(self.growth_obj)
        assert expected_fuelbeds == self.growth_obj.get('fuelbeds')

    def test_with_truncation(self):
        # TODO: implement
        pass

class TestEstimatorGetFromGeoJSON(BaseTestEstimatorEstimate):
    def setup(self):
        self.growth_obj = {"location": {"geojson": GEOJSON}}
        super(TestEstimatorGetFromGeoJSON, self).setup()

class TestEstimatorGetFromLatLng(BaseTestEstimatorEstimate):

    def setup(self):
        self.growth_obj = {"location": {"latitude": 46.0, 'longitude': -120.34}}
        super(TestEstimatorGetFromLatLng, self).setup()

##
## Tests for Estimator._truncate
##

class TestEstimatorTruncation(object):

    def setup(self):
        lookup = mock.Mock()
        self.estimator = fuelbeds.Estimator(lookup)


    # TDOO: UPDATE ALL THESE TESTS TO USE NEW CLASS INTERFACE


    def test_truncate_empty_set(self):
        growth_obj = dict(fuelbeds=[])
        self.estimator._truncate(growth_obj)
        assert [] == growth_obj['fuelbeds']

    def test_truncate_one_fuelbed(self):
        growth_obj = dict(fuelbeds=[{'fccs_id': 1, 'pct': 100}])
        self.estimator._truncate(growth_obj)
        assert [{'fccs_id': 1, 'pct': 100}] == growth_obj['fuelbeds']

        # a single fuelbed's percentage should never be below 100%,
        # let alone the truncation percemtage threshold, but code
        # should handle it
        pct = 99 - fuelbeds.Estimator.TRUNCATION_PERCENTAGE_THRESHOLD
        growth_obj = dict(fuelbeds=[{'fccs_id': 1, 'pct': pct}])
        self.estimator._truncate(growth_obj)
        assert [{'fccs_id': 1, 'pct': pct}] == growth_obj['fuelbeds']

    def test_truncate_multiple_fbs_no_truncation(self):
        growth_obj = dict(fuelbeds=[
            {'fccs_id': 1, 'pct': 50},
            {'fccs_id': 2, 'pct': 20},
            {'fccs_id': 3, 'pct': 30}
        ])
        self.estimator._truncate(growth_obj)
        expected = [
            {'fccs_id': 1, 'pct': 50},
            {'fccs_id': 3, 'pct': 30},
            {'fccs_id': 2, 'pct': 20}
        ]
        assert expected == growth_obj['fuelbeds']

    def test_truncate_multiple_fbs_truncated(self):
        growth_obj = dict(fuelbeds=[
            {'fccs_id': 3, 'pct': 20},
            {'fccs_id': 1, 'pct': 75},
            {'fccs_id': 2, 'pct': 5}
        ])
        self.estimator._truncate(growth_obj)
        expected = [
            {'fccs_id': 1, 'pct': 75},
            {'fccs_id': 3, 'pct': 20}
        ]
        assert expected == growth_obj['fuelbeds']
        growth_obj = dict(fuelbeds=[
            {'fccs_id': 5, 'pct': 16},
            {'fccs_id': 45, 'pct': 3},
            {'fccs_id': 1, 'pct': 75},
            {'fccs_id': 223, 'pct': 5},
            {'fccs_id': 3, 'pct': 1}
        ])
        self.estimator._truncate(growth_obj)
        expected = [
            {'fccs_id': 1, 'pct': 75},
            {'fccs_id': 5, 'pct': 16}
        ]
        assert expected == growth_obj['fuelbeds']

# ##
# ## Tests for Estimator._adjust_percentages
# ##

class TestEstimatorPercentageAdjustment(object):

    def setup(self):
        lookup = mock.Mock()
        self.estimator = fuelbeds.Estimator(lookup)

    def test_no_adjustment(self):
        pass

    def test_with_adjustment(self):
        pass
