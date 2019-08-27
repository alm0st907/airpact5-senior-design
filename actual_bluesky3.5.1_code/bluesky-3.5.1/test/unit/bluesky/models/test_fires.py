"""Unit tests for bluesky.models.fires"""

__author__ = "Joel Dubowy"

import copy
import datetime
import json
import sys
import io
import uuid

import freezegun

from py.test import raises
from numpy.testing import assert_approx_equal

from bluesky import __version__
from bluesky.models import fires

##
## Tests for Fire
##

class TestFire:

    def test_fills_in_id(self, monkeypatch):
        monkeypatch.setattr(uuid, "uuid1", lambda: "abcd1234")
        # if id is missing, the id is set to generated guid.
        # Note: id used to integrate start and/or end, if specified;
        #   this is no longer the case
        f = fires.Fire({"a": 123, "b": "sdf"})
        assert "abcd1234" == f["id"]
        f = fires.Fire({"a": 123, "b": "sdf", "start": "20120202 10:20:32"})
        assert "abcd1234" == f["id"]
        f = fires.Fire({"a": 123, "b": "sdf", "end": "20120922 10:20:32"})
        assert "abcd1234" == f["id"]
        f = fires.Fire({
            "a": 123, "b": "sdf",
            "start": "20120202 10:20:32", "end": "20120922T10:20:32"})
        assert "abcd1234" == f["id"]
        # if id exists, use it
        f = fires.Fire({
            "a": 123, "b": "sdf",
            "start": "20120202 10:20:32", "end": "20120922T10:20:32",
            "id": "sdkjfh2rkjhsdf"})
        assert "sdkjfh2rkjhsdf" == f["id"]

    def test_fills_in_or_validates_type_and_fuel_type(self):
        # defaults 'type' and 'fuel_type
        f = fires.Fire({"a": 123, "b": "sdf"})
        assert f['type'] == fires.Fire.DEFAULT_TYPE
        assert f['fuel_type'] == fires.Fire.DEFAULT_FUEL_TYPE

        # accepts 'type' and 'fuel_type values if specified and valid
        f = fires.Fire({"a": 123, "b": "sdf",
            "type": 'rx', 'fuel_type': 'piles'})
        assert f['type'] == 'rx'
        assert f['fuel_type'] == 'piles'

        # converts to lowercase
        f = fires.Fire({"a": 123, "b": "sdf",
            "type": 'Rx', 'fuel_type': 'PILES'})
        assert f['type'] == 'rx'
        assert f['fuel_type'] == 'piles'


        # validates 'type' on instantiation
        with raises(ValueError) as e_info:
            f = fires.Fire({"a": 123, "b": "sdf",
                "type": 'foo', 'fuel_type': 'piles'})
        assert e_info.value.args[0] == fires.Fire.INVALID_TYPE_MSG.format('foo')

        f = fires.Fire()

        # validates 'type' on setattr
        with raises(ValueError) as e_info:
            f.type = 'foo'
        assert e_info.value.args[0] == fires.Fire.INVALID_TYPE_MSG.format('foo')

        # validates 'type' on dict set
        with raises(ValueError) as e_info:
            f['type'] = 'foo'
        assert e_info.value.args[0] == fires.Fire.INVALID_TYPE_MSG.format('foo')

        # validates 'fuel_type' on instantiation
        with raises(ValueError) as e_info:
            f = fires.Fire({"a": 123, "b": "sdf",
                "type": 'rx', 'fuel_type': 'bar'})
        assert e_info.value.args[0] == fires.Fire.INVALID_FUEL_TYPE_MSG.format('bar')

        # validates 'fuel_type' on setattr
        with raises(ValueError) as e_info:
            f.fuel_type = 'bar'
        assert e_info.value.args[0] == fires.Fire.INVALID_FUEL_TYPE_MSG.format('bar')

        # validates 'fuel_type' on dict set
        with raises(ValueError) as e_info:
            f['fuel_type'] = 'bar'
        assert e_info.value.args[0] == fires.Fire.INVALID_FUEL_TYPE_MSG.format('bar')

    def test_accessing_attributes(self):
        f = fires.Fire({'a': 123, 'b': 'sdf'})
        assert 123 == f['a']
        assert 123 == f.a
        assert 'sdf' == f['b']
        assert 'sdf' == f.b
        with raises(KeyError) as e:
            f['sdfdsf']
        with raises(AttributeError) as e:
            f.rifsijsflj

    def test_start_and_end(self):
        # no growth windows
        f = fires.Fire({})
        assert None == f.start
        assert None == f.start_utc
        assert None == f.end
        assert None == f.end_utc
        # empty growth list
        f = fires.Fire({"growth": []})
        assert None == f.start
        assert None == f.start_utc
        assert None == f.end
        assert None == f.end_utc
        # one growth window with no 'start'
        f = fires.Fire({"growth": [{}]})
        assert None == f.start
        assert None == f.start_utc
        assert None == f.end
        assert None == f.end_utc
        # one growth window with None 'start'
        f = fires.Fire({"growth": [{'start': None}]})
        assert None == f.start
        assert None == f.start_utc
        assert None == f.end
        assert None == f.end_utc
        # multiple growth windows with no 'start'
        f = fires.Fire({"growth": [{}, {}]})
        assert None == f.start
        assert None == f.start_utc
        assert None == f.end
        assert None == f.end_utc
        # multiple growth windows with None 'start'
        f = fires.Fire({"growth": [{'start': None}, {'start': None}]})
        assert None == f.start
        assert None == f.start_utc
        assert None == f.end
        assert None == f.end_utc
        # multiple growth windows with None 'end'
        f = fires.Fire({"growth": [{'end': None}, {'end': None}]})
        assert None == f.start
        assert None == f.start_utc
        assert None == f.end
        assert None == f.end_utc
        # one growth window with start defined
        f = fires.Fire({"growth": [{'start': "2014-05-27T17:00:00"}]})
        assert datetime.datetime(2014,5,27,17,0,0) == f.start
        assert datetime.datetime(2014,5,27,17,0,0) == f.start_utc
        assert None == f.end
        assert None == f.end_utc
        # one growth window with end defined
        f = fires.Fire({"growth": [{'end': "2014-05-27T17:00:00"}]})
        assert None == f.start
        assert None == f.start_utc
        assert datetime.datetime(2014,5,27,17,0,0) == f.end
        assert datetime.datetime(2014,5,27,17,0,0) == f.end_utc
        # multiple growth windows, some with 'start' defined, some with end
        # defined, out of order
        f = fires.Fire({"growth": [
            {'start': None, 'end': '2014-05-30T17:00:00'},
            {'start': "2014-05-29T17:00:00", 'end': None},
            {'start': "2014-05-27T17:00:00", 'end': '2014-05-27T17:00:00'},
            {'start': None, 'end': None}
            ]})
        assert datetime.datetime(2014,5,27,17,0,0) == f.start
        assert datetime.datetime(2014,5,27,17,0,0) == f.start_utc
        assert datetime.datetime(2014,5,30,17,0,0) == f.end
        assert datetime.datetime(2014,5,30,17,0,0) == f.end_utc

        # multiple growth windows, all with 'start' & 'end' defined, out of order
        f = fires.Fire({"growth": [
            {'start': "2014-05-29T17:00:00", 'end': "2014-05-30T17:00:00"},
            {'start': "2014-05-27T17:00:00", 'end': "2014-05-28T17:00:00"},
            {'start': "2014-05-28T17:00:00", 'end': "2014-05-29T17:00:00"}
            ]})
        assert datetime.datetime(2014,5,27,17,0,0) == f.start
        assert datetime.datetime(2014,5,30,17,0,0) == f.end
        assert datetime.datetime(2014,5,27,17,0,0) == f.start_utc
        assert datetime.datetime(2014,5,30,17,0,0) == f.end_utc
        # multiple growth windows, all with 'start' & 'end' defined, out of
        # order, with utc_offset defined
        f = fires.Fire({
            "growth": [
                {
                    "location": {"utc_offset": '-07:00'},
                    'start': "2014-05-29T17:00:00",
                    'end': "2014-05-30T17:00:00"
                },
                {
                    "location": {"utc_offset": '-07:00'},
                    'start': "2014-05-27T17:00:00",
                    'end': "2014-05-28T17:00:00"
                },
                {
                    "location": {"utc_offset": '-07:00'},
                    'start': "2014-05-28T17:00:00",
                    'end': "2014-05-29T17:00:00"
                }
            ]
        })
        assert datetime.datetime(2014,5,27,17,0,0) == f.start
        assert datetime.datetime(2014,5,30,17,0,0) == f.end
        assert datetime.datetime(2014,5,28,0,0,0) == f.start_utc
        assert datetime.datetime(2014,5,31,0,0,0) == f.end_utc


##
## Tests for FiresManager
##

class TestFiresManager(object):

    ## Get/Set Fires and Meta

    def test_getting_fires_and_meta(self):
        fires_manager = fires.FiresManager()
        fire_objects = [
            fires.Fire({'id': '1', 'name': 'n1', 'dfd':'a1', 'baz':'baz1'}),
            fires.Fire({'id': '2', 'name': 'n2', 'bar':'a1', 'baz':'baz1'})
        ]
        fires_manager.fires = fire_objects
        fires_manager._meta = {'a':1, 'b':{'c':2}}

        assert fire_objects == fires_manager.fires
        assert 1 == fires_manager.a
        assert {'c':2} == fires_manager.b
        assert 2 == fires_manager.b['c']
        assert None == fires_manager.d

    @freezegun.freeze_time("2016-04-20")
    def test_setting_fires_and_meta(self):
        fires_manager = fires.FiresManager()
        fire_objects = [
            fires.Fire({'id': '1', 'name': 'n1', 'dfd':'a1', 'baz':'baz1'}),
            fires.Fire({'id': '2', 'name': 'n2', 'bar':'a1', 'baz':'baz1'})
        ]
        fires_manager.fires = fire_objects
        fires_manager.a = 1
        fires_manager.b = {'c': 2}
        # you can also set meta data directly
        fires_manager.meta['d'] = 123

        assert fires_manager.num_fires == 2
        assert set(['1','2']) == set(list(fires_manager._fires.keys()))
        assert {'1': [fire_objects[0]],'2': [fire_objects[1]]} == fires_manager._fires
        expected_meta = {
            'a':1, 'b':{'c':2}, 'd': 123,
            'today': freezegun.api.FakeDate(2016, 4, 20),
            'config': {}
        }
        assert expected_meta == fires_manager._meta == fires_manager.meta

    ## Properties

    @freezegun.freeze_time("2016-04-20")
    def test_today_is_processed_for_wildcards(self, monkeypatch):
        fm = fires.FiresManager()
        assert fm.today == datetime.date(2016,4,20)

        # test setting fm.today by load

        fm.load({'today': datetime.datetime(2012, 4,3,22,11)})
        assert fm.today == datetime.datetime(2012, 4,3,22,11)

        fm.load({'today': "2012-04-02T22:11:00Z"})
        assert fm.today == datetime.datetime(2012, 4,2,22,11)

        fm.load({'today': "{today}"})
        assert fm.today == datetime.datetime(2016, 4,20)

        fm.load({'today': "{yesterday}"})
        assert fm.today == datetime.datetime(2016, 4, 19)

        # TODO: any other possibilities ??

        # test setting fm.today by assignmentd

        fm.today = datetime.datetime(2016, 4, 1)
        assert fm.today == datetime.datetime(2016, 4, 1)

        fm.today = "2012-04-04T22:13:00Z"
        assert fm.today == datetime.datetime(2012, 4, 4, 22, 13)

        fm.today = "{today}"
        assert fm.today == datetime.datetime(2016, 4, 20)

        fm.today = "{yesterday}"
        assert fm.today == datetime.datetime(2016, 4, 19)

        # TODO: any other possibilities ??

    def test_run_id_is_immutable(self, monkeypatch):
        monkeypatch.setattr(uuid, 'uuid1', lambda: "sdf123")

        fm = fires.FiresManager()
        # if not already set, run_id is set when accessed
        assert fm.run_id == "sdf123"
        with raises(TypeError) as e_info:
            fm.run_id = "sdfsdfsdf"
        assert e_info.value.args[0] == fires.FiresManager.RUN_ID_IS_IMMUTABLE_MSG

        # FiresManager.load sets run_id
        fm = fires.FiresManager()
        fm.load({})
        assert fm.run_id == "sdf123"
        with raises(TypeError) as e_info:
            fm.run_id = "sdfsdfsdf"
        assert e_info.value.args[0] == fires.FiresManager.RUN_ID_IS_IMMUTABLE_MSG

        fm = fires.FiresManager()
        fm.load({'run_id': "ggbgbg"})
        assert fm.run_id == "ggbgbg"
        with raises(TypeError) as e_info:
            fm.run_id = "sdfsdfsdf"
        assert e_info.value.args[0] == fires.FiresManager.RUN_ID_IS_IMMUTABLE_MSG

        fm = fires.FiresManager(run_id="ggg")
        assert fm.run_id == "ggg"
        with raises(TypeError) as e_info:
            fm.run_id = "sdfsdfsdf"
        assert e_info.value.args[0] == fires.FiresManager.RUN_ID_IS_IMMUTABLE_MSG

        fm = fires.FiresManager()
        fm.run_id = "eee"
        assert fm.run_id == "eee"
        with raises(TypeError) as e_info:
            fm.run_id = "sdfsdfsdf"
        assert e_info.value.args[0] == fires.FiresManager.RUN_ID_IS_IMMUTABLE_MSG

        # when you load, fm starts from scratch
        assert fm.run_id == "eee"
        fm = fires.FiresManager()
        fm.load({'run_id': "ggbgbg"})
        assert fm.run_id == "ggbgbg"

    def test_earliest_and_latest_times(self):
        fm = fires.FiresManager()
        f1 = fires.Fire({
            'id': '1',
            'growth': [
                {
                    "start": "2014-05-27T17:00:00",
                    "end": "2014-05-28T17:00:00",
                    'location': {'area': 34, 'latitude': 45.0, 'longitude': -120.0},
                },
                {
                    "start": "2014-05-25T17:00:00",
                    "end": "2014-05-26T17:00:00",
                    'location': {'area': 34, 'latitude': 45.0, 'longitude': -120.0},
                }
            ]
        })
        f2 = fires.Fire({
            'id': '2',
            "growth":[
                {
                    "start": "2014-05-27T19:00:00",
                    "end": "2014-05-28T19:00:00",
                    'location': {'area': 132, 'latitude': 45.0, 'longitude': -120.0},
                }
            ]
        })
        f3 = fires.Fire({
            'id': '2',
        })
        fm.fires = [f1, f2, f3]
        assert datetime.datetime(2014,5,25,17) == fm.earliest_start
        assert datetime.datetime(2014,5,28,19) == fm.latest_end

        # same thing, but with time zones specified for two of the fires
        f1.growth[0]['location']['utc_offset'] = '-07:00'
        f1.growth[1]['location']['utc_offset'] = '-07:00'
        f2.growth[0]['location']['utc_offset'] = '03:00' # no longer the latest time
        assert datetime.datetime(2014,5,26,0) == fm.earliest_start
        assert datetime.datetime(2014,5,29,0) == fm.latest_end

    ## Loading

    def _stream(test_self, data=''):
        def _stream(self, file_name, flag):
            if flag == 'r':
                return io.StringIO(data)
            else:
                test_self._output = io.StringIO()
                return test_self._output
        return _stream

    def test_load_invalid_data(self, monkeypatch):
        fires_manager = fires.FiresManager()

        monkeypatch.setattr(fires.FiresManager, '_stream', self._stream(''))
        with raises(ValueError):
            fires_manager.loads()

        monkeypatch.setattr(fires.FiresManager, '_stream', self._stream('""'))
        with raises(ValueError):
            fires_manager.loads()

        monkeypatch.setattr(fires.FiresManager, '_stream', self._stream('"sdf"'))
        with raises(ValueError):
            fires_manager.loads()

        monkeypatch.setattr(fires.FiresManager, '_stream', self._stream('null'))
        with raises(ValueError):
            fires_manager.loads()

    @freezegun.freeze_time("2016-04-20")
    def test_load_no_fires_no_meta(self, monkeypatch):
        fires_manager = fires.FiresManager()
        expected_meta = {
            "today": datetime.date(2016,4,20),
            'config':{}
        }

        monkeypatch.setattr(fires.FiresManager, '_stream', self._stream('{}'))
        fires_manager.loads()
        assert fires_manager.num_fires == 0
        assert [] == fires_manager.fires
        assert expected_meta == fires_manager.meta

        monkeypatch.setattr(fires.FiresManager, '_stream', self._stream('{"fire_information":[]}'))
        fires_manager.loads()
        assert [] == fires_manager.fires
        assert expected_meta == fires_manager.meta

    @freezegun.freeze_time("2016-04-20")
    def test_load_no_fires_with_meta(self, monkeypatch):
        fires_manager = fires.FiresManager()
        monkeypatch.setattr(fires.FiresManager, '_stream', self._stream(
            '{"fire_information":[], "foo": {"bar": "baz"}}'))
        fires_manager.loads()
        assert fires_manager.num_fires == 0
        assert [] == fires_manager.fires
        expected_meta = {
            "today": datetime.date(2016,4,20),
            'config':{},
            "foo": {"bar": "baz"}
        }
        assert expected_meta == fires_manager.meta

    @freezegun.freeze_time("2016-04-20")
    def test_load_one_fire_with_meta(self, monkeypatch):
        fires_manager = fires.FiresManager()
        monkeypatch.setattr(fires.FiresManager, '_stream', self._stream(
            '{"fire_information":[{"id":"a","bar":123,"baz":12.32,"bee":"12.12"}],'
            '"foo": {"bar": "baz"}}'))
        fires_manager.loads()
        expected_fires = [
            fires.Fire({'id':'a', 'bar':123, 'baz':12.32, 'bee': "12.12"})
        ]
        assert fires_manager.num_fires == 1
        assert expected_fires == fires_manager.fires
        expected_meta = {
            "today": datetime.date(2016,4,20),
            'config':{},
            "foo": {"bar": "baz"}
        }
        assert expected_meta == fires_manager.meta

    @freezegun.freeze_time("2016-04-20")
    def test_load_multiple_fires_with_meta(self, monkeypatch):
        fires_manager = fires.FiresManager()
        monkeypatch.setattr(fires.FiresManager, '_stream', self._stream(
            '{"fire_information":[{"id":"a","bar":123,"baz":12.32,"bee":"12.12"},'
            '{"id":"b","bar":2, "baz": 1.1, "bee":"24.34"}],'
            '"foo": {"bar": "baz"}}'))
        #monkeypatch.setattr(uuid, "uuid1", lambda: "abcd1234")
        fires_manager.loads()
        expected_fires = [
            fires.Fire({'id':'a', 'bar':123, 'baz':12.32, 'bee': "12.12"}),
            fires.Fire({'id':'b', 'bar':2, 'baz': 1.1, 'bee': '24.34'})
        ]
        assert fires_manager.num_fires == 2
        assert expected_fires == fires_manager.fires
        expected_meta = {
            #"run_id": 'abcd1234'
            "today": datetime.date(2016,4,20),
            'config':{},
            "foo": {"bar": "baz"},
        }
        assert expected_meta == fires_manager.meta

    ## Dumping

    def test_dump_no_fire_no_meta(self, monkeypatch):
        pass

    def test_dump_no_fires_with_meta(self, monkeypatch):
        pass

    def test_dump_one_fire_with_meta(self, monkeypatch):
        pass

    @freezegun.freeze_time("2016-04-20")
    def test_dump_multiple_fires_with_meta(self, monkeypatch):
        fires_manager = fires.FiresManager()
        monkeypatch.setattr(fires.FiresManager, '_stream', self._stream())
        fire_objects = [
            fires.Fire({'id':'a', 'bar':123, 'baz':12.32, 'bee': "12.12"}),
            fires.Fire({'id':'b', 'bar':2, 'baz': 1.1, 'bee': '24.34'})
        ]
        fires_manager.fires = fire_objects
        fires_manager.foo = {"bar": "baz"}

        fires_manager.dumps()
        expected = {
            "today": "2016-04-20",
            "config": {},
            "fire_information": fire_objects,
            "foo": {"bar": "baz"},
            "counts": {
                "fires": 2
            },
            "bluesky_version": __version__
        }

        assert expected == json.loads(self._output.getvalue())

    # TODO: test instantiating with fires, dump, adding more with loads, dump, etc.

    ## Failures

    def test_fire_failure_handler(self):
        def go(fire):
            if fire.id == '2':
                raise RuntimeError("oops")

        # Skip
        fires_manager = fires.FiresManager()
        fires_manager.fires = [
            fires.Fire({'id': '1', 'name': 'n1'}),
            fires.Fire({'id': '2', 'name': 'n2'})
        ]
        assert fires_manager.num_fires == 2
        fires_manager.config = {"skip_failed_fires": True}
        assert fires_manager.skip_failed_fires
        for fire in fires_manager.fires:
            with fires_manager.fire_failure_handler(fire):
                go(fire)
        assert fires_manager.fires == [
            fires.Fire({'id': '1', 'name': 'n1'})
        ]
        assert fires_manager.num_fires == 1
        assert len(fires_manager.failed_fires) == 1
        assert fires_manager.failed_fires[0].id == '2'
        assert fires_manager.failed_fires[0].name == 'n2'
        assert fires_manager.failed_fires[0]['error']['message'] == 'oops'
        assert fires_manager.failed_fires[0]['error']['traceback']

        # Don't Skip
        fires_manager = fires.FiresManager()
        fires_manager.fires = [
            fires.Fire({'id': '1', 'name': 'n1'}),
            fires.Fire({'id': '2', 'name': 'n2'})
        ]
        fires_manager.config = {"skip_failed_fires": False}
        assert fires_manager.num_fires == 2
        assert not fires_manager.skip_failed_fires
        for fire in fires_manager.fires:
            if fire.id == '1':
                with fires_manager.fire_failure_handler(fire):
                    go(fire)
            else:
                with raises(RuntimeError) as e_info:
                    with fires_manager.fire_failure_handler(fire):
                        go(fire)
        assert fires_manager.num_fires == 2
        assert len(fires_manager.fires) == 2
        assert fires_manager.fires[0] == fires.Fire({'id': '1', 'name': 'n1'})
        assert fires_manager.fires[1].id == '2'
        assert fires_manager.fires[1].name == 'n2'
        assert fires_manager.fires[1]['error']['message'] == 'oops'
        assert fires_manager.fires[1]['error']['traceback']
        assert fires_manager.failed_fires is None


##
## Tests for setting configuration (to make sure filecards get
## filled in, etc.) and merging
##

class TestFiresManagerSetAndMergeConfig(object):

    # TODO: USe freeze fun or set 'today', and then use
    # various '{(today:yesterday)[:patterm]}' in config settings

    RAW_CONFIG = {
        "foo":"bar",
        "bar": "{today}-sdf-{yesterday:%Y-%m-%d}T12Z-%Y__%m-%d-{today-2:%m_%d}-",
        "baz": 234,
        "foobar": "2016-10-11",
        "barbaz": "{today-1}",
        "foobarbaz": "{datetime-parse-buster}2016-10-11",
        "barbazfoo": "{datetime-parse-buster}{today-1}"
    }
    CONFIG_2016_05_04 = {
        "foo":"bar",
        "bar": "20160504-sdf-2016-05-03T12Z-%Y__%m-%d-05_02-",
        "baz": 234,
        "foobar": datetime.datetime(2016,10,11),
        "barbaz": datetime.datetime(2016,5,3),
        "foobarbaz": "2016-10-11",
        "barbazfoo": "20160503"
    }
    CONFIG_2016_05_05 = {
        "foo":"bar",
        "bar": "20160505-sdf-2016-05-04T12Z-%Y__%m-%d-05_03-",
        "baz": 234,
        "foobar": datetime.datetime(2016,10,11),
        "barbaz": datetime.datetime(2016,5,4),
        "foobarbaz": "2016-10-11",
        "barbazfoo": "20160504"
    }
    def test_setting_config_manually(self):
        fm = fires.FiresManager()
        fm.today = datetime.datetime(2016, 5, 4)
        fm.config = copy.deepcopy(self.RAW_CONFIG)
        assert fm.config == self.CONFIG_2016_05_04
        fm.today = datetime.datetime(2016, 5, 5)
        assert fm.config == self.CONFIG_2016_05_05
        # TODO: set fm.today = datetime.datetime(2016, 5, 5) again
        #   and make sure (by capturing method calls) that config
        #   doesn't get reprocessed

    def test_loading_config(self):
        fm = fires.FiresManager()
        fm.load({
            'today': datetime.datetime(2016, 5, 4),
            'config': copy.deepcopy(self.RAW_CONFIG)
        })
        assert fm.config == self.CONFIG_2016_05_04
        fm.today = datetime.datetime(2016, 5, 5)
        assert fm.config == self.CONFIG_2016_05_05
        # TODO: set fm.today = datetime.datetime(2016, 5, 5) again
        #   and make sure (by capturing method calls) that config
        #   doesn't get reprocessed

    def test_merge_configs(self):
        fm = fires.FiresManager()

        fm.merge_config({
            "foo": {
                "a": 111,
                "b": 222,
                "c": 333,
                "d": 444
            }
        })
        EXPECTED = {
            "foo": {
                "a": 111,
                "b": 222,
                "c": 333,
                "d": 444
            }
        }
        assert fm.config == EXPECTED

        fm.merge_config({
            "foo": {
                "b": 2222,
                "c": 3333,
                "d": 4444,
                "bb": "bb"
            },
            "bar": {
                "b": "b"
            },
            "b": "b"
        })
        EXPECTED = {
            "foo": {
                "a": 111,
                "b": 2222,
                "c": 3333,
                "d": 4444,
                "bb": "bb"
            },
            "bar": {
                "b": "b"
            },
            "b": "b"
        }
        assert fm.config == EXPECTED

        fm.merge_config({
            "foo": {
                "c": 33333,
                "d": 44444,
                "cc": "cc"
            },
            "baz": {
                "c": "c"
            },
            "c": "c"
        })
        EXPECTED = {
            "foo": {
                "a": 111,
                "b": 2222,
                "c": 33333,
                "d": 44444,
                "bb": "bb",
                "cc": "cc"
            },
            "bar": {
                "b": "b"
            },
            "baz": {
                "c": "c"
            },
            "b": "b",
            "c": "c"
        }
        assert fm.config == EXPECTED

        fm.set_config_value("444444", 'foo', 'd')
        fm.set_config_value("dd", 'foo', 'dd')
        fm.set_config_value("d", 'boo', 'd')
        fm.set_config_value("d", 'd')
        fm.set_config_value(True, 'dbt')
        fm.set_config_value(False, 'dbf')
        fm.set_config_value(23, 'di')
        fm.set_config_value(123.23, 'df')
        fm.set_config_value('23', 'dci')
        fm.set_config_value('123.23', 'dcf')
        EXPECTED = {
            "foo": {
                "a": 111,
                "b": 2222,
                "c": 33333,
                "d": "444444", # because it was set on command line
                "bb": "bb",
                "cc": "cc",
                "dd": "dd"
            },
            "bar": {
                "b": "b"
            },
            "baz": {
                "c": "c"
            },
            "boo": {
                "d": "d"
            },
            "b": "b",
            "c": "c",
            "d": "d",
            "dbt": True,
            "dbf": False,
            "di": 23,
            "df": 123.23,
            "dci": "23",
            "dcf": "123.23"
        }
        assert fm.config == EXPECTED


##
## Tests for Merging
##
## TODO: unit test fires.FiresMerger directly
##

class TestFiresManagerMergeFires(object):

    def test_no_fires(self):
        fm = fires.FiresManager()
        assert fm.num_fires == 0
        assert fm.fires == []
        fm.merge_fires()
        assert fm.num_fires == 0
        assert fm.fires == []

    def test_one_fire(self):
        fm = fires.FiresManager()
        f = fires.Fire({'id': '1'})
        fm.fires = [f]
        assert fm.num_fires == 1
        assert fm.fires == [f]
        fm.merge_fires()
        assert fm.num_fires == 1
        assert fm.fires == [f]

    def test_none_to_merge(self):
        fm = fires.FiresManager()
        f = fires.Fire({'id': '1'})
        f2 = fires.Fire({'id': '2'})
        fm.fires = [f, f2]
        assert fm.num_fires == 2
        assert fm.fires == [f, f2]
        fm.merge_fires()
        assert fm.num_fires == 2
        assert fm.fires == [f, f2]

    def test_simple(self):
        fm = fires.FiresManager()
        f = fires.Fire({'id': '1'})
        f2 = fires.Fire({'id': '1'})
        fm.fires = [f, f2]
        fm.num_fires == 1
        assert dict(fm.fires[0]) == {
            'id': '1',
            'fuel_type': fires.Fire.DEFAULT_FUEL_TYPE,
            'type': fires.Fire.DEFAULT_TYPE
        }

    def test_invalid_keys(self):
        # test in both skip and no-skip modes
        for s in (True, False):
            # i.e. top-level location is old structure
            fm = fires.FiresManager()
            fm.set_config_value(s, 'merge', 'skip_failures')
            f = fires.Fire({'id': '1', 'location': {'area': 132}})
            f2 = fires.Fire({'id': '1', 'location': {'area': 132}})
            fm.fires = [f, f2]
            if not s:
                with raises(ValueError) as e_info:
                    fm.merge_fires()
                assert fm.num_fires == 2
                assert e_info.value.args[0].index(fires.FiresMerger.INVALID_KEYS_MSG) > 0
            else:
                fm.merge_fires()
                assert fm.num_fires == 2
                assert [f, f2] == sorted(fm.fires, key=lambda e: int(e.id))

    def test_growth_for_only_one_fire(self):
        # test in both skip and no-skip modes
        for s in (True, False):
            fm = fires.FiresManager()
            fm.set_config_value(s, 'merge', 'skip_failures')
            f = fires.Fire({
                'id': '1'
            })
            f2 = fires.Fire({
                'id': '1',
                "growth":[
                    {
                        "start": "2014-05-27T17:00:00",
                        "end": "2014-05-28T17:00:00",
                        "pct": 100.0,
                        'location': {
                            'area': 132,
                            'latitude': 45.0,
                            'longitude': -120.0
                        }
                    }
                ]
            })
            fm.fires = [f, f2]
            if not s:
                with raises(ValueError) as e_info:
                    fm.merge_fires()
                assert fm.num_fires == 2
                assert e_info.value.args[0].index(
                    fires.FiresMerger.GROWTH_FOR_BOTH_OR_NONE_MSG) > 0
            else:
                fm.merge_fires()
                assert fm.num_fires == 2
                assert [f, f2] == sorted(fm.fires, key=lambda e: int('growth' in e))

    def test_overlapping_growth(self):
        # TODO: implemented once check is in place
        pass

    def test_different_event_ids(self):
        # test in both skip and no-skip modes
        for s in (True, False):
            fm = fires.FiresManager()
            fm.set_config_value(s, 'merge', 'skip_failures')
            f = fires.Fire({
                'id': '1',
                "event_of":{
                    "id": "ABC"
                },
                # growth just used for assertion, below
                "growth": [{"location":{'area': 123}}]
            })
            f2 = fires.Fire({
                'id': '1',
                "event_of":{
                    "id": "SDF"
                },
                # growth just used for assertion, below
                "growth": [{"location":{'area': 456}}]
            })
            fm.fires = [f, f2]
            if not s:
                with raises(ValueError) as e_info:
                    fm.merge_fires()
                assert fm.num_fires == 2
                assert e_info.value.args[0].index(fires.FiresMerger.EVENT_MISMATCH_MSG) > 0
            else:
                fm.merge_fires()
                assert fm.num_fires == 2
                assert [f, f2] == sorted(fm.fires, key=lambda e: int(e.growth[0]['location']['area']))

    def test_different_fire_and_fuel_type(self):
        # test in both skip and no-skip modes
        for s in (True, False):
            fm = fires.FiresManager()
            fm.set_config_value(s, 'merge', 'skip_failures')
            f = fires.Fire({
                'id': '1',
                "type": "rx",
                "fuel_type": "natural",
                # growth just used for assertion, below
                "growth": [{"location":{'area': 123}}]
            })
            f2 = fires.Fire({
                'id': '1',
                "type": "wf",
                "fuel_type": "natural",
                # growth just used for assertion, below
                "growth": [{"location":{'area': 456}}]
            })
            fm.fires = [f, f2]
            assert fm.num_fires == 2

            if not s:
                with raises(ValueError) as e_info:
                    fm.merge_fires()
                assert fm.num_fires == 2
                assert e_info.value.args[0].index(fires.FiresMerger.FIRE_TYPE_MISMATCH_MSG) > 0
            else:
                fm.merge_fires()
                assert fm.num_fires == 2
                assert [f, f2] == sorted(fm.fires, key=lambda e: int(e.growth[0]['location']['area']))

            f2.type = f.type
            f2.fuel_type = "activity"
            fm.fires = [f, f2]
            assert fm.num_fires == 2
            if not s:
                with raises(ValueError) as e_info:
                    fm.merge_fires()
                assert fm.num_fires == 2
                assert e_info.value.args[0].index(fires.FiresMerger.FUEL_TYPE_MISMATCH_MSG) > 0
            else:
                fm.merge_fires()
                assert fm.num_fires == 2
                assert [f, f2] == sorted(fm.fires, key=lambda e: int(e.growth[0]['location']['area']))

    def test_merge_mixed_success_no_growth(self):
        fm = fires.FiresManager()
        #fm.set_config_value(True, 'merge', 'skip_failures')
        f = fires.Fire({
            'id': '1',
            "type": "rx",
            "fuel_type": "natural"
        })
        f2 = fires.Fire({
            'id': '1',
            "type": "rx",
            "fuel_type": "natural"
        })
        f3 = fires.Fire({
            'id': '2',
            "type": "rx",
            "fuel_type": "natural"
        })
        fm.fires = [f, f2, f3]
        assert fm.num_fires == 3
        fm.merge_fires()
        expected = [
            fires.Fire({
                'id': '1',
                "type": "rx",
                "fuel_type": "natural"
            }),
            fires.Fire({
                'id': '2',
                "type": "rx",
                "fuel_type": "natural"
            })
        ]
        assert fm.num_fires == 2
        assert expected == sorted(fm.fires, key=lambda e: int(e.id))

    def test_merge_mixed_success(self):
        fm = fires.FiresManager()
        #fm.set_config_value(True, 'merge', 'skip_failures')
        f = fires.Fire({
            'id': '1',
            "type": "rx",
            "fuel_type": "natural",
            "growth": [
                {
                    "start": "2014-05-28T17:00:00",
                    "end": "2014-05-29T17:00:00",
                    'location': {
                        'area': 90,
                        'latitude': 45.0,
                        'longitude': -120.0
                    }
                },
                {
                    "start": "2014-05-29T17:00:00",
                    "end": "2014-05-30T17:00:00",
                    'location': {
                        'area': 90,
                        'latitude': 46.0,
                        'longitude': -120.0
                    }
                }
            ]
        })
        f2 = fires.Fire({
            'id': '1',
            "type": "rx",
            "fuel_type": "natural",
            "growth": [
                {
                    "start": "2014-05-27T17:00:00",
                    "end": "2014-05-28T17:00:00",
                    'location': {
                        'area': 10,
                        'latitude': 45.0,
                        'longitude': -120.0
                    }
                }
            ]
        })
        f3 = fires.Fire({
            'id': '2',
            "type": "rx",
            "fuel_type": "natural",
            "growth": [
                {
                    "start": "2014-05-27T17:00:00",
                    "end": "2014-05-30T17:00:00",
                    'location': {
                        'area': 132,
                        'latitude': 45.0,
                        'longitude': -120.0
                    }
                }
            ]
        })
        fm.fires = [f, f2, f3]
        assert fm.num_fires == 3
        fm.merge_fires()
        assert fm.num_fires == 2
        expected = [
            fires.Fire({
                'id': '1',
                "type": "rx",
                "fuel_type": "natural",
                "growth": [
                    {
                        "start": "2014-05-27T17:00:00",
                        "end": "2014-05-28T17:00:00",
                        'location': {
                            'area': 10,
                            'latitude': 45.0,
                            'longitude': -120.0
                        }
                    },
                    {
                        "start": "2014-05-28T17:00:00",
                        "end": "2014-05-29T17:00:00",
                        'location': {
                            'area': 90,
                            'latitude': 45.0,
                            'longitude': -120.0
                        }
                    },
                    {
                        "start": "2014-05-29T17:00:00",
                        "end": "2014-05-30T17:00:00",
                        'location': {
                            'area': 90,
                            'latitude': 46.0,
                            'longitude': -120.0
                        }
                    }
                ]
            }),
            fires.Fire({
                'id': '2',
                "type": "rx",
                "fuel_type": "natural",
                "growth": [
                    {
                        "start": "2014-05-27T17:00:00",
                        "end": "2014-05-30T17:00:00",
                        'location': {
                            'area': 132,
                            'latitude': 45.0,
                            'longitude': -120.0
                        }
                    }
                ]
            })
        ]
        actual = sorted(fm.fires, key=lambda e: int(e.id))
        assert expected == actual


##
## Tests for Filtering
##
## TODO: unit test fires.FireGrowthFilter directly
##

class TestFiresManagerFilterFires(object):


    ## Filtering

    def test_no_filters_specified(self):
        fm = fires.FiresManager()
        init_fires = [
            fires.Fire({'id': '1', 'name': 'n1', 'dfd':'a1', 'baz':'baz1'}),
        ]
        fm.fires = init_fires

        ## No filters specifeid
        fm.set_config_value(False, 'filter', 'skip_failures')
        with raises(fires.FireGrowthFilter.FilterError) as e_info:
            fm.filter_fires()
        assert fm.num_fires == 1
        assert e_info.value.args[0] == fires.FireGrowthFilter.NO_FILTERS_MSG
        fm.set_config_value(True, 'filter', 'skip_failures')
        fm.filter_fires()
        assert fm.num_fires == 1
        assert init_fires == sorted(fm.fires, key=lambda e: int(e.id))


    def test_filter_by_country(self):
        fm = fires.FiresManager()
        init_fires = [
            fires.Fire({'id': '01', 'name': 'n1', 'dfd':'a1', 'baz':'baz1'}),
            fires.Fire({'id': '02', 'name': 'n2', 'bar':'a1', 'baz':'baz1'}),
            fires.Fire({'id': '03', 'name': 'n3', 'bar1':'a1', 'baz':'baz1',
                "growth": [{"location": {'country': "ZZ"}}, {"location": {'country': "ZZ"}}]}),
            fires.Fire({'id': '04', 'name': 'n4', 'bar1':'a1', 'baz':'baz1',
                "growth": [{"location": {'country': "UK"}}]}),
            fires.Fire({'id': '05', 'name': 'n5', 'bar1':'a1', 'baz':'baz1',
                "growth": [{"location": {'country': "USA"}}]}),
            fires.Fire({'id': '06', 'name': 'n6', 'bar1': 1 , 'baz':'baz1',
                "growth": [{"location": {'country': ''}}]}),
            fires.Fire({'id': '07', 'name': 'n7', 'bar2':'a2', 'baz':'baz2',
                "growth": [{"location": {'country': "CA"}}]}),
            fires.Fire({'id': '08', 'name': 'n8', 'bar2':'adfsdf', 'baz':'baz2',
                "growth": [{"location": {'country': "CA"}}]}),
            fires.Fire({'id': '09', 'name': 'n9', 'bar2': 2 , 'baz':'baz2',
                "growth": [{"location": {'country': 'Unknown'}}]}),
            fires.Fire({'id': '10', 'name': 'n10', "barj": "jj", "baz": 99,
                "growth": [{"location": {"country": "USA"}}]}),
            fires.Fire({'id': '11', 'name': 'n11', "barj": "jj", "baz": 99,
                "growth": [{"location": {"country": "BZ"}}]}),
            fires.Fire({'id': '12', 'name': 'n3', 'bar1':'a1', 'baz':'baz1',
                "growth": [{"location": {'country': "ZZ"}}, {"location": {'country': "UK"}}]}),
            fires.Fire({'id': '13', 'name': 'n3', 'bar1':'a1', 'baz':'baz1',
                "growth": [{"location": {'country': "ZZ"}}, {"location": {'country': "ZZ"}}]}),
        ]
        fm.fires = init_fires
        assert fm.num_fires == 13

        ## empty config
        fm.set_config_value({}, 'filter', 'country')
        fm.set_config_value(False, 'filter', 'skip_failures')
        with raises(fires.FireGrowthFilter.FilterError) as e_info:
            fm.filter_fires()
        assert fm.num_fires == 13
        assert e_info.value.args[0] == fires.FireGrowthFilter.MISSING_FILTER_CONFIG_MSG
        fm.set_config_value(True, 'filter', 'skip_failures')
        fm.filter_fires()
        assert fm.num_fires == 13
        assert init_fires == sorted(fm.fires, key=lambda e: int(e.id))

        ## Neither whitelist nor blacklist is specified
        fm.set_config_value({'foo': 'bar'}, 'filter', 'country')
        fm.set_config_value(False, 'filter', 'skip_failures')
        with raises(fires.FireGrowthFilter.FilterError) as e_info:
            fm.filter_fires()
        assert fm.num_fires == 13
        assert e_info.value.args[0] == fires.FireGrowthFilter.SPECIFY_WHITELIST_OR_BLACKLIST_MSG
        fm.set_config_value(True, 'filter', 'skip_failures')
        fm.filter_fires()
        assert fm.num_fires == 13
        assert init_fires == sorted(fm.fires, key=lambda e: int(e.id))

        ## Both whitelist nor blacklist are specified
        fm.set_config_value(False, 'filter', 'skip_failures')
        fm.set_config_value(["ZZ"], 'filter', 'country', 'blacklist')
        fm.set_config_value(["YY"], 'filter', 'country', 'whitelist')
        with raises(fires.FireGrowthFilter.FilterError) as e_info:
            fm.filter_fires()
        assert fm.num_fires == 13
        assert e_info.value.args[0] == fires.FireGrowthFilter.SPECIFY_WHITELIST_OR_BLACKLIST_MSG
        fm.set_config_value(True, 'filter', 'skip_failures')
        fm.filter_fires()
        assert fm.num_fires == 13
        assert init_fires == sorted(fm.fires, key=lambda e: int(e.id))

        fm.set_config_value(False, 'filter', 'skip_failures')
        fm.set_config_value(["ZZ"], 'filter', 'country', 'blacklist')
        fm.set_config_value(None, 'filter', 'country', 'whitelist')
        fm.filter_fires()
        expected = [
            fires.Fire({'id': '04', 'name': 'n4', 'bar1':'a1', 'baz':'baz1',
                "growth": [{"location": {'country': "UK"}}]}),
            fires.Fire({'id': '05', 'name': 'n5', 'bar1':'a1', 'baz':'baz1',
                "growth": [{"location": {'country': "USA"}}]}),
            fires.Fire({'id': '06', 'name': 'n6', 'bar1': 1 , 'baz':'baz1',
                "growth": [{"location": {'country': ''}}]}),
            fires.Fire({'id': '07', 'name': 'n7', 'bar2':'a2', 'baz':'baz2',
                "growth": [{"location": {'country': "CA"}}]}),
            fires.Fire({'id': '08', 'name': 'n8', 'bar2':'adfsdf', 'baz':'baz2',
                "growth": [{"location": {'country': "CA"}}]}),
            fires.Fire({'id': '09', 'name': 'n9', 'bar2': 2 , 'baz':'baz2',
                "growth": [{"location": {'country': 'Unknown'}}]}),
            fires.Fire({'id': '10', 'name': 'n10', "barj": "jj", "baz": 99,
                "growth": [{"location": {"country": "USA"}}]}),
            fires.Fire({'id': '11', 'name': 'n11', "barj": "jj", "baz": 99,
                "growth": [{"location": {"country": "BZ"}}]}),
            fires.Fire({'id': '12', 'name': 'n3', 'bar1':'a1', 'baz':'baz1',
                "growth": [{"location": {'country': "UK"}}]}),
        ]
        assert fm.num_fires == 9
        assert expected == sorted(fm.fires, key=lambda e: int(e.id))

        fm.set_config_value(["USA", "CA", "UK", "BZ"],
            'filter', 'country', 'whitelist')
        fm.set_config_value(None, 'filter', 'country', 'blacklist')
        fm.filter_fires()
        expected = [
            fires.Fire({'id': '04', 'name': 'n4', 'bar1':'a1', 'baz':'baz1',
                "growth": [{"location": {'country': "UK"}}]}),
            fires.Fire({'id': '05', 'name': 'n5', 'bar1':'a1', 'baz':'baz1',
                "growth": [{"location": {'country': "USA"}}]}),
            fires.Fire({'id': '07', 'name': 'n7', 'bar2':'a2', 'baz':'baz2',
                "growth": [{"location": {'country': "CA"}}]}),
            fires.Fire({'id': '08', 'name': 'n8', 'bar2':'adfsdf', 'baz':'baz2',
                "growth": [{"location": {'country': "CA"}}]}),
            fires.Fire({'id': '10', 'name': 'n10', "barj": "jj", "baz": 99,
                "growth": [{"location": {"country": "USA"}}]}),
            fires.Fire({'id': '11', 'name': 'n11', "barj": "jj", "baz": 99,
                "growth": [{"location": {"country": "BZ"}}]}),
            fires.Fire({'id': '12', 'name': 'n3', 'bar1':'a1', 'baz':'baz1',
                "growth": [{"location": {'country': "UK"}}]})
        ]
        assert fm.num_fires == 7
        assert expected == sorted(fm.fires, key=lambda e: int(e.id))

        fm.set_config_value(["USA"], 'filter', 'country', 'blacklist')
        fm.set_config_value(None, 'filter', 'country', 'whitelist')
        fm.filter_fires()
        expected = [
            fires.Fire({'id': '04', 'name': 'n4', 'bar1':'a1', 'baz':'baz1',
                "growth": [{"location": {'country': "UK"}}]}),
            fires.Fire({'id': '07', 'name': 'n7', 'bar2':'a2', 'baz':'baz2',
                "growth": [{"location": {'country': "CA"}}]}),
            fires.Fire({'id': '08', 'name': 'n8', 'bar2':'adfsdf', 'baz':'baz2',
                "growth": [{"location": {'country': "CA"}}]}),
            fires.Fire({'id': '11', 'name': 'n11', "barj": "jj", "baz": 99,
                "growth": [{"location": {"country": "BZ"}}]}),
            fires.Fire({'id': '12', 'name': 'n3', 'bar1':'a1', 'baz':'baz1',
                "growth": [{"location": {'country': "UK"}}]})
        ]
        assert fm.num_fires == 5
        assert expected == sorted(fm.fires, key=lambda e: int(e.id))

        fm.set_config_value(["USA", "CA", "UK"], 'filter', 'country', 'whitelist')
        fm.set_config_value(None, 'filter', 'country', 'blacklist')
        fm.filter_fires()
        expected = [
            fires.Fire({'id': '04', 'name': 'n4', 'bar1':'a1', 'baz':'baz1',
                "growth": [{"location": {'country': "UK"}}]}),
            fires.Fire({'id': '07', 'name': 'n7', 'bar2':'a2', 'baz':'baz2',
                "growth": [{"location": {'country': "CA"}}]}),
            fires.Fire({'id': '08', 'name': 'n8', 'bar2':'adfsdf', 'baz':'baz2',
                "growth": [{"location": {'country': "CA"}}]}),
            fires.Fire({'id': '12', 'name': 'n3', 'bar1':'a1', 'baz':'baz1',
                "growth": [{"location": {'country': "UK"}}]})
        ]
        assert fm.num_fires == 4
        assert expected == sorted(fm.fires, key=lambda e: int(e.id))

        fm.set_config_value(["USA", "CA"], 'filter', 'country', 'blacklist')
        fm.set_config_value(None, 'filter', 'country', 'whitelist')
        fm.filter_fires()
        expected = [
            fires.Fire({'id': '04', 'name': 'n4', 'bar1':'a1', 'baz':'baz1',
                "growth": [{"location": {'country': "UK"}}]}),
            fires.Fire({'id': '12', 'name': 'n3', 'bar1':'a1', 'baz':'baz1',
                "growth": [{"location": {'country': "UK"}}]})
        ]
        assert fm.num_fires == 2
        assert expected == fm.fires

        fm.set_config_value(["UK", "CA"], 'filter', 'country', 'blacklist')
        fm.set_config_value(None, 'filter', 'country', 'whitelist')
        fm.filter_fires()
        assert fm.num_fires == 0
        assert [] == fm.fires

        # call again with no fires
        fm.filter_fires()
        assert fm.num_fires == 0
        assert [] == fm.fires

    def test_filter_by_location(self):

        fm = fires.FiresManager()
        init_fires = [
            fires.Fire({'id': '1', 'growth': [{'location':{'latitude': 40.0, 'longitude': -80.0}}]}),
            fires.Fire({'id': '2', 'growth': [{'location':{'latitude': 50.0, 'longitude': -80.0}}]}),
            fires.Fire({'id': '3', 'growth': [{'location':{'latitude': 60.0, 'longitude': -62.0}}]}),
            fires.Fire({'id': '4', 'growth': [{'location':{'latitude': 70.0, 'longitude': -60.0}}]}),
            fires.Fire({'id': '5', 'growth': [{'location':{'latitude': 40.0, 'longitude': -60.0}}]}),
            fires.Fire({'id': '6', 'growth': [{'location':{'latitude': 61.0, 'longitude': -60.0}}]}),
            fires.Fire({'id': '7', 'growth': [{'location':{'latitude': 60.0, 'longitude': -50.0}}]}),
            fires.Fire({'id': '8', 'growth': [{'location':{'latitude': 70.0, 'longitude': -120.0}}]}),
            fires.Fire({'id': '9', 'growth': [{'location':{'latitude': -10.0, 'longitude': 10.0}}]}),
            fires.Fire({'id': '10', 'growth': [{'location':{'latitude': -10.0, 'longitude': 10.0}},
                {'location':{'latitude': 40.0, 'longitude': -80.0}}]}),
            fires.Fire({'id': '10', 'growth': [{'location':{'latitude': -10.0, 'longitude': 10.0}},
                {'location':{'latitude': -11.0, 'longitude': 9.0}}]})
        ]
        fm.fires = init_fires
        assert fm.num_fires == 11

        ## Failure situations
        scenarios = (
            # empty config
            ({}, fires.FireGrowthFilter.MISSING_FILTER_CONFIG_MSG),
            # boundary not specified
            ({'foo': 'bar'}, fires.FireGrowthFilter.SPECIFY_BOUNDARY_MSG),

            ## Invalid boundary
            # Invalid and insufficient keys
            ({'boundary': {"foo": "bar"}},
                fires.FireGrowthFilter.INVALID_BOUNDARY_FIELDS_MSG),
            # Invalid keys
            ({'boundary': {
                "sdfsdf": 123,
                "ne": {"lat": 88.12, "lng": 40},
                "sw": {"lat": -50.75,"lng": -131.5}}},
                fires.FireGrowthFilter.INVALID_BOUNDARY_FIELDS_MSG),
            # insufficient keys
            ({'boundary': {
                "ne": {"lng": 40},
                "sw": {"lat": -50.75,"lng": -131.5}}},
                fires.FireGrowthFilter.INVALID_BOUNDARY_FIELDS_MSG),
            ({'boundary': {
                "sw": {"lat": -50.75,"lng": -131.5}}},
                fires.FireGrowthFilter.INVALID_BOUNDARY_FIELDS_MSG),
            # lat/lng outside of valid range
            ({'boundary': {
                "ne": {"lat": 98.12, "lng": 40},
                "sw": {"lat": -50.75,"lng": -131.5}}},
                fires.FireGrowthFilter.INVALID_BOUNDARY_MSG),
            # sw east of ne
            ({'boundary': {
                "ne": {"lat": 68.12, "lng": 40},
                "sw": {"lat": 50.75,"lng": 50.5}}},
                fires.FireGrowthFilter.INVALID_BOUNDARY_MSG),
            # sw north of ne
            ({'boundary': {
                "ne": {"lat": 48.12, "lng": 40},
                "sw": {"lat": 50.75,"lng": -50.5}}},
                fires.FireGrowthFilter.INVALID_BOUNDARY_MSG)
        )
        for config, err_msg in scenarios:
            fm.set_config_value(config, 'filter', 'location')
            # don't skip failures
            fm.set_config_value(False, 'filter', 'skip_failures')
            with raises(fires.FireGrowthFilter.FilterError) as e_info:
                fm.filter_fires()
            assert fm.num_fires == 11
            assert init_fires == sorted(fm.fires, key=lambda e: int(e.id))
            assert e_info.value.args[0] == err_msg
            # skip failures
            fm.set_config_value(True, 'filter', 'skip_failures')
            fm.filter_fires()
            assert fm.num_fires == 11
            assert init_fires == sorted(fm.fires, key=lambda e: int(e.id))

        ## noops
        fm.set_config_value({"ne": {"lat": 88.12, "lng": 40},
            "sw": {"lat": -50.75,"lng": -131.5}},
            'filter', 'location', 'boundary')
        fm.filter_fires()
        assert fm.num_fires == 11
        assert init_fires == sorted(fm.fires, key=lambda e: int(e.id))

        ## successful filters
        # squeeze sw lat
        fm.set_config_value({"ne": {"lat": 88.12, "lng": 40},
            "sw": {"lat": -5.75,"lng": -131.5}},
            'filter', 'location', 'boundary')
        expected = [
            fires.Fire({'id': '1', 'growth': [{'location':{'latitude': 40.0, 'longitude': -80.0}}]}),
            fires.Fire({'id': '2', 'growth': [{'location':{'latitude': 50.0, 'longitude': -80.0}}]}),
            fires.Fire({'id': '3', 'growth': [{'location':{'latitude': 60.0, 'longitude': -62.0}}]}),
            fires.Fire({'id': '4', 'growth': [{'location':{'latitude': 70.0, 'longitude': -60.0}}]}),
            fires.Fire({'id': '5', 'growth': [{'location':{'latitude': 40.0, 'longitude': -60.0}}]}),
            fires.Fire({'id': '6', 'growth': [{'location':{'latitude': 61.0, 'longitude': -60.0}}]}),
            fires.Fire({'id': '7', 'growth': [{'location':{'latitude': 60.0, 'longitude': -50.0}}]}),
            fires.Fire({'id': '8', 'growth': [{'location':{'latitude': 70.0, 'longitude': -120.0}}]}),
            fires.Fire({'id': '10', 'growth': [{'location':{'latitude': 40.0, 'longitude': -80.0}}]})
        ]
        fm.filter_fires()
        assert fm.num_fires == 9
        assert expected == sorted(fm.fires, key=lambda e: int(e.id))

        # squeeze sw lng
        fm.set_config_value({"ne": {"lat": 88.12, "lng": 40},
            "sw": {"lat": -5.75,"lng": -110.5}},
            'filter', 'location', 'boundary')
        expected = [
            fires.Fire({'id': '1', 'growth': [{'location':{'latitude': 40.0, 'longitude': -80.0}}]}),
            fires.Fire({'id': '2', 'growth': [{'location':{'latitude': 50.0, 'longitude': -80.0}}]}),
            fires.Fire({'id': '3', 'growth': [{'location':{'latitude': 60.0, 'longitude': -62.0}}]}),
            fires.Fire({'id': '4', 'growth': [{'location':{'latitude': 70.0, 'longitude': -60.0}}]}),
            fires.Fire({'id': '5', 'growth': [{'location':{'latitude': 40.0, 'longitude': -60.0}}]}),
            fires.Fire({'id': '6', 'growth': [{'location':{'latitude': 61.0, 'longitude': -60.0}}]}),
            fires.Fire({'id': '7', 'growth': [{'location':{'latitude': 60.0, 'longitude': -50.0}}]}),
            fires.Fire({'id': '10', 'growth': [{'location':{'latitude': 40.0, 'longitude': -80.0}}]})
        ]
        fm.filter_fires()
        assert fm.num_fires == 8
        assert expected == sorted(fm.fires, key=lambda e: int(e.id))

        # squeeze ne lat
        fm.set_config_value({"ne": {"lat": 66.12, "lng": 40},
            "sw": {"lat": -5.75,"lng": -110.5}},
            'filter', 'location', 'boundary')
        expected = [
            fires.Fire({'id': '1', 'growth': [{'location':{'latitude': 40.0, 'longitude': -80.0}}]}),
            fires.Fire({'id': '2', 'growth': [{'location':{'latitude': 50.0, 'longitude': -80.0}}]}),
            fires.Fire({'id': '3', 'growth': [{'location':{'latitude': 60.0, 'longitude': -62.0}}]}),
            fires.Fire({'id': '5', 'growth': [{'location':{'latitude': 40.0, 'longitude': -60.0}}]}),
            fires.Fire({'id': '6', 'growth': [{'location':{'latitude': 61.0, 'longitude': -60.0}}]}),
            fires.Fire({'id': '7', 'growth': [{'location':{'latitude': 60.0, 'longitude': -50.0}}]}),
            fires.Fire({'id': '10', 'growth': [{'location':{'latitude': 40.0, 'longitude': -80.0}}]})
        ]
        fm.filter_fires()
        assert fm.num_fires == 7
        assert expected == sorted(fm.fires, key=lambda e: int(e.id))

        # squeeze ne lng
        fm.set_config_value({"ne": {"lat": 66.12, "lng": -55},
            "sw": {"lat": -5.75,"lng": -110.5}},
            'filter', 'location', 'boundary')
        expected = [
            fires.Fire({'id': '1', 'growth': [{'location':{'latitude': 40.0, 'longitude': -80.0}}]}),
            fires.Fire({'id': '2', 'growth': [{'location':{'latitude': 50.0, 'longitude': -80.0}}]}),
            fires.Fire({'id': '3', 'growth': [{'location':{'latitude': 60.0, 'longitude': -62.0}}]}),
            fires.Fire({'id': '5', 'growth': [{'location':{'latitude': 40.0, 'longitude': -60.0}}]}),
            fires.Fire({'id': '6', 'growth': [{'location':{'latitude': 61.0, 'longitude': -60.0}}]}),
            fires.Fire({'id': '10', 'growth': [{'location':{'latitude': 40.0, 'longitude': -80.0}}]})
        ]
        fm.filter_fires()
        assert fm.num_fires == 6
        assert expected == sorted(fm.fires, key=lambda e: int(e.id))

        # squeeze ne lng
        fm.set_config_value({"ne": {"lat": 63.12, "lng": -61},
            "sw": {"lat": 58.75,"lng": -62}},
            'filter', 'location', 'boundary')
        expected = [
            fires.Fire({'id': '3', 'growth': [{'location':{'latitude': 60.0, 'longitude': -62.0}}]})
        ]
        fm.filter_fires()
        assert fm.num_fires == 1
        assert expected == sorted(fm.fires, key=lambda e: int(e.id))

        # squeeze out last fire
        fm.set_config_value({"ne": {"lat": 63.12, "lng": -61},
            "sw": {"lat": 60.75,"lng": -62}},
            'filter', 'location', 'boundary')
        fm.filter_fires()
        assert fm.num_fires == 0
        assert [] == sorted(fm.fires, key=lambda e: int(e.id))

        # call again with no fires
        fm.filter_fires()
        assert fm.num_fires == 0
        assert [] == sorted(fm.fires, key=lambda e: int(e.id))

        ## Invalid fire
        fm.set_config_value({"ne": {"lat": 88.12, "lng": 40},
            "sw": {"lat": -50.75,"lng": -131.5}},
            'filter', 'location', 'boundary')
        scenarios = (
            # missing lat
            (fires.Fire({'id': '1', 'growth': [{'location':{'longitude': -80.0}}]}),
             fires.FireGrowthFilter.MISSING_FIRE_LAT_LNG_MSG),
            # missing lng
            (fires.Fire({'id': '1', 'growth': [{'location':{'longitude': -80.0}}]}),
             fires.FireGrowthFilter.MISSING_FIRE_LAT_LNG_MSG),
            # missing both lat and lng
            (fires.Fire({'id': '1', 'growth': [{'location':{}}]}),
             fires.FireGrowthFilter.MISSING_FIRE_LAT_LNG_MSG),
            # missing location
            (fires.Fire({'id': '1', 'growth': [{}]}),
             fires.FireGrowthFilter.MISSING_FIRE_LAT_LNG_MSG),
        )
        for f, err_msg in scenarios:
            fm.fires = [f]
            # don't skip failures
            fm.set_config_value(False, 'filter', 'skip_failures')
            with raises(fires.FireGrowthFilter.FilterError) as e_info:
                fm.filter_fires()
            assert fm.num_fires == 1
            assert [f] == fm.fires
            assert e_info.value.args[0].index(err_msg) > 0
            # skip failures
            fm.set_config_value(True, 'filter', 'skip_failures')
            fm.filter_fires()
            assert fm.num_fires == 1
            assert [f] == fm.fires


    def test_filter_by_area(self):

        fm = fires.FiresManager()
        init_fires = [
            fires.Fire({'id': '1', 'growth': [{'location':{'area': 45}}]}),
            fires.Fire({'id': '2', 'growth': [{'location':{'area': 95}}]}),
            fires.Fire({'id': '3', 'growth': [{'location':{'area': 55}}]}),
            fires.Fire({'id': '4', 'growth': [{'location':{'area': 65}}]}),
            fires.Fire({'id': '5', 'growth': [{'location':{'area': 85}}]}),
            fires.Fire({'id': '6', 'growth': [{'location':{'area': 75}}]}),
            fires.Fire({'id': '7', 'growth': [{'location':{'area': 50}}]}),
            fires.Fire({'id': '8', 'growth': [{'location':{'area': 30}}]}),
            fires.Fire({'id': '9', 'growth': [{'location':{'area': 45}},
                {'location':{'area': 40}}]})
        ]
        fm.fires = init_fires
        assert fm.num_fires == 9

        ## Failure situations
        scenarios = (
            # empty config
            ({}, fires.FireGrowthFilter.MISSING_FILTER_CONFIG_MSG),
            # either min nor max is specified
            ({'foo': 'bar'}, fires.FireGrowthFilter.SPECIFY_MIN_OR_MAX_MSG),

            ## Invalid min/max
            # both negative
            ({'min': -20, 'max': -2},
                fires.FireGrowthFilter.INVALID_MIN_MAX_MUST_BE_POS_MSG),
            # min is negative
            ({'min': -20, 'max': 2},
                fires.FireGrowthFilter.INVALID_MIN_MAX_MUST_BE_POS_MSG),
            ({'min': -20},
                fires.FireGrowthFilter.INVALID_MIN_MAX_MUST_BE_POS_MSG),
            # max is negative
            ({'min': 20, 'max': -2},
                fires.FireGrowthFilter.INVALID_MIN_MAX_MUST_BE_POS_MSG),
            ({'max': -2},
                fires.FireGrowthFilter.INVALID_MIN_MAX_MUST_BE_POS_MSG),
            # min > max
            ({'min': 20, 'max': 2},
                fires.FireGrowthFilter.INVALID_MIN_MUST_BE_LTE_MAX_MSG),
        )
        for config, err_msg in scenarios:
            fm.set_config_value(config, 'filter', 'area')
            # don't skip failures
            fm.set_config_value(False, 'filter', 'skip_failures')
            with raises(fires.FireGrowthFilter.FilterError) as e_info:
                fm.filter_fires()
            assert fm.num_fires == 9
            assert init_fires == sorted(fm.fires, key=lambda e: int(e.id))
            assert e_info.value.args[0] == err_msg
            # skip failures
            fm.set_config_value(True, 'filter', 'skip_failures')
            fm.filter_fires()
            assert fm.num_fires == 9
            assert init_fires == sorted(fm.fires, key=lambda e: int(e.id))

        ## noops
        fm.set_config_value(False, 'filter', 'skip_failures')
        # min only
        fm.set_config_value({'min': 20}, 'filter', 'area')
        fm.filter_fires()
        assert fm.num_fires == 9
        assert init_fires == sorted(fm.fires, key=lambda e: int(e.id))
        # max only
        fm.set_config_value({'max': 120}, 'filter', 'area')
        fm.filter_fires()
        assert fm.num_fires == 9
        assert init_fires == sorted(fm.fires, key=lambda e: int(e.id))
        # both min and max
        fm.set_config_value({'min': 20, 'max': 120}, 'filter', 'area')
        fm.filter_fires()
        assert fm.num_fires == 9
        assert init_fires == sorted(fm.fires, key=lambda e: int(e.id))

        ## successful filters
        # min only
        fm.set_config_value({'min': 47}, 'filter', 'area')
        expected = [
            fires.Fire({'id': '2', 'growth': [{'location':{'area': 95}}]}),
            fires.Fire({'id': '3', 'growth': [{'location':{'area': 55}}]}),
            fires.Fire({'id': '4', 'growth': [{'location':{'area': 65}}]}),
            fires.Fire({'id': '5', 'growth': [{'location':{'area': 85}}]}),
            fires.Fire({'id': '6', 'growth': [{'location':{'area': 75}}]}),
            fires.Fire({'id': '7', 'growth': [{'location':{'area': 50}}]})
        ]
        fm.filter_fires()
        assert fm.num_fires == 6
        assert expected == sorted(fm.fires, key=lambda e: int(e.id))
        # max only
        fm.set_config_value({'max': 90}, 'filter', 'area')
        expected = [
            fires.Fire({'id': '3', 'growth': [{'location':{'area': 55}}]}),
            fires.Fire({'id': '4', 'growth': [{'location':{'area': 65}}]}),
            fires.Fire({'id': '5', 'growth': [{'location':{'area': 85}}]}),
            fires.Fire({'id': '6', 'growth': [{'location':{'area': 75}}]}),
            fires.Fire({'id': '7', 'growth': [{'location':{'area': 50}}]})
        ]
        fm.filter_fires()
        assert fm.num_fires == 5
        assert expected == sorted(fm.fires, key=lambda e: int(e.id))

        # both min and max
        fm.set_config_value({'min': 52, 'max': 77.0}, 'filter', 'area')
        expected = [
            fires.Fire({'id': '3', 'growth': [{'location':{'area': 55}}]}),
            fires.Fire({'id': '4', 'growth': [{'location':{'area': 65}}]}),
            fires.Fire({'id': '6', 'growth': [{'location':{'area': 75}}]})
        ]
        fm.filter_fires()
        assert fm.num_fires == 3
        assert expected == sorted(fm.fires, key=lambda e: int(e.id))

        # both min and max
        fm.set_config_value({'min': 65, 'max': 65.0}, 'filter', 'area')
        expected = [
            fires.Fire({'id': '4', 'growth': [{'location':{'area': 65}}]})
        ]
        fm.filter_fires()
        assert fm.num_fires == 1
        assert expected == sorted(fm.fires, key=lambda e: int(e.id))

        # filter out the rest
        fm.set_config_value({'min': 76, 'max': 77.0}, 'filter', 'area')
        fm.filter_fires()
        assert fm.num_fires == 0
        assert [] == sorted(fm.fires, key=lambda e: int(e.id))

        # call again with no fires
        fm.filter_fires()
        assert fm.num_fires == 0
        assert [] == sorted(fm.fires, key=lambda e: int(e.id))

        ## Invalid fire
        fm.set_config_value({'min': 0.0, 'max': 100.0}, 'filter', 'area')
        scenarios = (
            # missing area
            (fires.Fire({'id': '1', 'growth':[{'location':{}}]}),
             fires.FireGrowthFilter.MISSING_GROWTH_AREA_MSG),
            # missing location
            (fires.Fire({'id': '1', 'growth':[{}]}),
             fires.FireGrowthFilter.MISSING_GROWTH_AREA_MSG),
            # negative area
            (fires.Fire({'id': '1', 'growth':[{'location':{'area': -123}}]}),
             fires.FireGrowthFilter.NEGATIVE_GROWTH_AREA_MSG),
        )
        for f, err_msg in scenarios:
            fm.fires = [f]
            # don't skip failures
            fm.set_config_value(False, 'filter', 'skip_failures')
            with raises(fires.FireGrowthFilter.FilterError) as e_info:
                fm.filter_fires()
            assert fm.num_fires == 1
            assert [f] == fm.fires
            assert e_info.value.args[0].index(err_msg) > 0
            # skip failures
            fm.set_config_value(True, 'filter', 'skip_failures')
            fm.filter_fires()
            assert fm.num_fires == 1
            assert [f] == fm.fires
