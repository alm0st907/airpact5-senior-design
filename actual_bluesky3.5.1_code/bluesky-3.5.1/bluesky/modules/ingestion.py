"""bluesky.modules.ingestion

Inputs data in a variety of formats, and produces data structured like the
following:

{
    "fire_information": [
        {
            "event_of": {
                "id": "SF11E826544",
                "name": "Natural Fire near Yosemite, CA"
            },
            "id": "SF11C14225236095807750",
            "type": "wildfire",
            "growth": [
                {
                    "start": "2014-05-29T17:00:00",
                    "end": "2014-05-30T17:00:00",
                    "location": {
                        "area": 10000,
                        "ecoregion": "western",
                        "latitude": 37.909644,
                        "longitude": -119.7615805,
                        "utc_offset": "-07:00"
                    }
                }
            ]
        },
        {
            "event_of": {
                "id": "sdfkj234kljfd",
                "name": "Natural Fire in North Tahoe"
            },
            "id": "sdk2risodijfdsf",
            "type": "wildfire",
            "growth": [
                {
                    "start": "2014-05-29T17:00:00",
                    "end": "2014-05-30T17:00:00",
                    "location": {
                        "ecoregion": "western",
                        "utc_offset": "-07:00",
                        "geojson": {
                            "type": "MultiPolygon",
                            "coordinates": [
                                [
                                    [
                                        [-121.4522115, 47.4316976],
                                        [-121.3990506, 47.4316976],
                                        [-121.3990506, 47.4099293],
                                        [-121.4522115, 47.4099293],
                                        [-121.4522115, 47.4316976]
                                    ]
                                ]
                            ]
                        }
                    }
                }
            ]
        }
    ]
}

# Supported Input formats:

 1) Data already structured like that above
 2) Flat dict; e.g.:

        {
            "area": 199.999999503,
            "latitude": 26.286,
            "longitude": -77.118,
            "date_time": "201405290000Z",
            ...
        }
 3) Deprecated bluesky fire structure; e.g.
        {
            "id": "SF11C14225236095807750",
            "event_of": {
                "id": "sdfkj234kljfd",
                "name": "Prescribed burn in the bahamas"
            },
            "type": "Rx",
            "location": {
                "latitude": 25.041,
                "longitude": -77.379,
                "area": 99.9999997516,
                "ecoregion": "western",
                "utc_offset": "-05:00"
            },
            "growth": [
                {
                    "start": "2015-01-20T19:00:00",
                    "end": "2015-01-21T19:00:00"
                }
            ]
        }

  4) Hybrids of the above formats; e.g.
        {
            "id": "SF11C14225236095807750",
            "event_id": "SF11E826544",
            "name": "Prescribed burn in the bahamas",
            "type": "Rx",
            "location": {
                "latitude": 25.041,
                "longitude": -77.379,
                "area": 99.9999997516,
                "ecoregion": "western",
                "utc_offset": "-05:00"
            },
            "growth": [
                {
                    "start": "2015-01-20T19:00:00",
                    "end": "2015-01-21T19:00:00"
                }
            ]
        }
"""

__author__ = "Joel Dubowy"

import copy
import datetime
import logging
import re

from bluesky import consumeutils

__all__ = [
    'run'
]

__version__ = "0.1.0"

def run(fires_manager):
    """Ingests the fire data, recording a copy of the raw input and restructuring
    the data as necessary

    Args:
     - fires_manager -- bluesky.models.fires.FiresManager object

    Note: The input being recorded may not be purely 'raw', since any fire
      lacking an id will have one auto-generated during Fire object
      instantiation.  Otherwise, what's recorded is the user's input.

    Note: Ingestion typically should only be run once, but the code does *not*
      enforce this.
    """
    logging.info("Running ingestion module")
    try:
        parsed_input = []
        fire_ingester = FireIngester()
        for fire in fires_manager.fires:
            with fires_manager.fire_failure_handler(fire):
                parsed_input.append(fire_ingester.ingest(fire))

        fires_manager.processed(__name__, __version__, parsed_input=parsed_input)
    except:
        # just record what module was run; the error will be inserted
        # into output data by calling code
        fires_manager.processed(__name__, __version__)
        raise


class IngestionErrMsgs(object):
    MULTIPLE_GROWTH_NO_PCT = ("Growth percentage, 'pct', must be"
        " defined if there are more than one growth objects"
        " and location is defined at the fire's top level.")

    NO_DATA = "Fire contains no data"

    ONE_GEOJSON_MULTIPLE_GROWTH = ("Can't assign fire GeoJSON to mutiple "
        "growth windows")

    BASE_LOCATION_AT_TOP_OR_PER_GROWTH = ("GeoJSON or lat+lng+area must be "
        "defined for the entire fire or for each growth object, not both")

    FUELBEDS_AT_TOP_OR_PER_GROWTH = ("Fuelbeds may be defined for the entire "
        "fire or for each growth object, or for neither, not both")

    NO_GROWTH_OR_BASE_LOCATION = ("GeoJSON or lat+lng+area must be defined"
        " for the entire fire if no growth windows are defined")

    MISSING_GROWH_FIELD = "Missing growth field: '{}'"


OPTIONAL_LOCATION_FIELDS = [
    "ecoregion",
    # utc_offset is for the most part required by modules using met data
    # (but not exclusively; e.g. FEPS plumerise uses it)
    "utc_offset",
    # SF2 weather, moisture, etc. fields
    'elevation','slope',
    'state','county','country',
    # TODO: should we ignore moisture fields, unless we're going to
    #   translate them to a formate that bsp recognizes?
    'moisture_1hr','moisture_10hr',
    'moisture_100hr','moisture_1khr',
    'moisture_live','moisture_duff',
    # TODO: should we ignore meteorological fields, unless we're going to
    #   translate them to a formate that bsp recognizes?
    'min_wind','max_wind',
    'min_wind_aloft', 'max_wind_aloft',
    'min_humid','max_humid',
    'min_temp','max_temp',
    'min_temp_hour','max_temp_hour',
    'sunrise_hour','sunset_hour',
    'snow_month','rain_days'
    # Ignore SF2 fuel category fields, since bsp computes them
    #   'fuel_1hr','fuel_10hr','fuel_100hr',
    #   'fuel_1khr','fuel_10khr','fuel_gt10khr',
    #   'canopy','shrub','grass','rot','duff', 'litter', 'VEG',
    # Ignore SF2 consumption, heat, and emissions fields, since bsp
    # will calculate them:
    #   'consumption_flaming', 'consumption_smoldering',
    #   'consumption_residual', 'consumption_duff', 'heat',
    #   'pm2.5', 'pm10', 'co', 'co2', 'ch4', 'nox', 'nh3', 'so2', 'voc'
    # Ignore 'timezone' here. (There's a TODO, below, to use it)
    # Other SF2 fields are mentioned in a TODO, below
]
for a in list(consumeutils.SETTINGS.values()):
    for b in a:
        OPTIONAL_LOCATION_FIELDS.append(b['field'])
        if 'synonyms' in b:
            OPTIONAL_LOCATION_FIELDS.extend(b['synonyms'])
# remove dupes
OPTIONAL_LOCATION_FIELDS = list(set(OPTIONAL_LOCATION_FIELDS))

GEOJSON_AREA_GEOMETRIES = ('Polygon', 'MultiPolygon')


class FireIngester(object):
    """Inputs, transforms, and validates fire data, recording original copy
    under 'input' key.

    Currently, for synonyms, you need to create a '_ingest_special_field_*'
    method to rename and record the field in the correct place.

    TODO: add more generic logic to handle simple fields with possible
      synonyms. e.g.

        SYNONYMS = {
            # field, section (optional), synonyms (optional)
            ("foo", None, None),
            ("bar", "location", None),
            ("baz", None, ["baaz", "baaaaz"])
        }

        for field, section, synonyms in SYNONYMS:
            v = None
            for f in [field] + (synonyms or []):
                v = self._get_field(f, section)
                if v:
                    break
            if v:
                if section:
                    if 'section' not in fire:
                        fire['section'] = {}
                    fire['section'][field] = v
                else:
                    fire[field] = v

      and, if necessary, refactor to support arbitrary section nesting
    """

    SCALAR_FIELDS = {
        "id", "type", "fuel_type"
    }
    # TODO: do anything with other fields found in daily SF2 data
    #     > 'owner','sf_event_guid','sf_server','sf_stream_name','fips','scc'

    NESTED_FIELD_METHOD_PREFIX = '_ingest_nested_field_'
    SPECIAL_FIELD_METHOD_PREFIX = '_ingest_special_field_'

    ##
    ## Public Interface
    ##

    # TODO: refact

    def ingest(self, fire):
        if not fire:
            raise ValueError(IngestionErrMsgs.NO_DATA)

        # move original data under 'input key'
        self._parsed_input = { k: fire.pop(k) for k in list(fire.keys()) }

        # copy back down any recognized top level, 'scalar' fields
        for k in self.SCALAR_FIELDS:
            if k in self._parsed_input:
                fire[k] = self._parsed_input[k]

        # Call separate ingest methods for each nested object
        for k in dir(self):
            if k.startswith(self.NESTED_FIELD_METHOD_PREFIX):
                getattr(self, k)(fire)

        # Ingest special fields; it's important that this happens after
        # the above ingest method calls
        for k in dir(self):
            if k.startswith(self.SPECIAL_FIELD_METHOD_PREFIX):
                getattr(self, k)(fire)

        self._ingest_custom_fields(fire)
        self._set_defaults(fire)

        FirePostProcessor(fire).process()

        return self._parsed_input

    ##
    ## General Helper methods
    ##

    def _ingest_custom_fields(self, fire):
        # TODO: copy over custom fields specified in config (need to pass
        # ingestion config settings into FireIngester constructor)
        pass

    def _set_defaults(self, fire):
        # TODO: set defaults for any fields that aren't defined; make the
        # defaults configurable, and maybe hard code any
        pass

    def _get_field(self, key, section=None):
        """Looks up field's value in fire object.

        Looks in 'input' > section > key, if section is defined. If not, or if
        key wasn't defined under the section, looks in top level fire object.

        TODO: support synonyms? (ex. what fields are called in fire_locations.csv)
        """
        v = None
        if section:
            v = self._parsed_input.get(section, {}).get(key)
        if v is None:
            v = self._parsed_input.get(key)
        return v

    def _get_fields(self, section, optional_fields):
        """Returns dict of specified fields, defined either in top level or
        nested within specified section

        Excludes any fields that are undefined or empty.
        """
        fields = {}
        for k in optional_fields:
            v = self._get_field(k, section)
            if v is not None:
                fields[k] = v
        return fields

    ##
    ## Nested Field Specific Ingest Methods
    ##

    ## 'location'

    def _get_base_location_object(self, GeoJSON, lat, lng, area):
        if GeoJSON:
            l = {
                'geojson': GeoJSON
            }
            if area:
                l['area'] = area
                return l
            elif GeoJSON.get('type') in GEOJSON_AREA_GEOMETRIES:
                return l
            else:
                # other geometry types require area, so this is invalid
                return {}

        elif lat is not None and lng is not None and area:
            return {
                'latitude': lat,
                'longitude': lng,
                'area': area
            }
        else:
            # We'll check later to ensure that lat/lng + area or GeoJSON is
            # specified either in top level or per growth object (but not both)
            return {}


    def _ingest_nested_field_location(self, fire):
        # TODO: validate fields

        # look for fields either in 'location' key or at top level
        fire['location'] = self._get_base_location_object(
            self._get_field('geojson', 'location'),
            self._get_field('latitude', 'location'),
            self._get_field('longitude', 'location'),
            self._get_field('area', 'location')
        )

        fire['location'].update(self._get_fields('location',
            OPTIONAL_LOCATION_FIELDS))

    ## 'event_of'

    def _ingest_nested_field_event_of(self, fire):
        event_of_fields = [
            # 'name' can be defined at the top level as well as under 'event_of'
            ("name", self._get_field("name", 'event_of')),
            # event id, if defined, can be defined as 'event_id' at the top
            # level or as 'id' under 'event_of'
            ("id", self._parsed_input.get('event_of', {}).get('id') or
                self._parsed_input.get('event_id')),
            # event url, if defined, can be defined as 'event_url' at the top
            # level or as 'url' under 'event_of'
            ("url", self._parsed_input.get('event_of', {}).get('url') or
                self._parsed_input.get('event_url'))
        ]
        event_of_dict = { k:v for k, v in event_of_fields if v}

        if event_of_dict:
            fire['event_of'] = event_of_dict

    ## 'growth'

    OPTIONAL_GROWTH_FIELDS = ['start','end', 'pct', 'localmet', 'timeprofile', 'plumerise']

    def _ingest_growth_location(self, growth, src):
        # only look in growth object for location fields; don't look
        base_fields = []
        for f in ['geojson', 'latitude', 'longitude', 'area']:
            v = src.get(f)
            if v is None and 'location' in src:
                v = src['location'].get(f)
            base_fields.append(v)
        location = self._get_base_location_object(*base_fields)

        for f in OPTIONAL_LOCATION_FIELDS:
            v = src.get(f)
            if v is None and 'location' in src:
                v = src['location'].get(f)
                if v is not None:
                    location[f] = v
        growth[-1]['location'] = location

    def _ingest_optional_growth_fields(self, growth, src):
        for f in self.OPTIONAL_GROWTH_FIELDS:
            v = src.get(f)
            if v:
                growth[-1][f] = v

    def _ingest_nested_field_growth(self, fire):
        # Note: can't use _get_field[s] as is because 'growth' is an array,
        # not a nested object
        growth = []
        if not self._parsed_input.get('growth'):
            # no growth array - look for 'start'/'end' in top level
            start = self._parsed_input.get('start')
            end = self._parsed_input.get('end')
            if start and end:
                growth.append({'start': start, 'end': end, 'pct': 100.0})
                self._ingest_optional_growth_fields(growth, self._parsed_input)

        else:
            for g in self._parsed_input['growth']:
                growth.append({})
                self._ingest_optional_growth_fields(growth, g)
                self._ingest_growth_location(growth, g)
                # TODO: make sure calling _ingest_nested_field_fuelbeds on g
                #   has the desired effect
                self._ingest_nested_field_fuelbeds(g)

        if growth:
            if len(growth) == 1 and 'pct' not in growth[0]:
                growth[0]['pct'] = 100.0
            # TODO: make sure percentages add up to 100.0, with allowable error
            fire['growth'] = growth

    ## 'fuelbeds'

    OPTIONAL_FUELBED_FIELDS = [
        'fccs_id', 'pct', 'fuel_loadings',
        'consumption', 'emissions', 'emissions_details'
    ]
    # TODO: do anything with fuelbed related data found in daily SF2 data ?
    #   e.g.:
    #     > consumption_flaming,consumption_smoldering,consumption_residual,
    #     > consumption_duff, heat,pm25,pm10,co,co2,ch4,nox,nh3,so2,voc,
    #     > fccs_number,veg

    def _ingest_nested_field_fuelbeds(self, fire):
        if self._parsed_input.get('fuelbeds'):
            fuelbeds = []
            for fb in self._parsed_input['fuelbeds']:
                fuelbed = {}
                for f in self.OPTIONAL_FUELBED_FIELDS:
                    v = fb.get(f)
                    if v:
                        fuelbed[f] = v
                if fuelbed:
                    fuelbeds.append(fuelbed)

            if fuelbeds:
                fire['fuelbeds'] = fuelbeds

    ## 'meta'

    def _ingest_nested_field_meta(self, fire):
        # just copy all of 'meta', if it's defined
        if self._parsed_input.get('meta'):
            fire['meta'] = copy.deepcopy(self._parsed_input['meta'])

    ##
    ## Special Field Ingest Methods
    ##

    # TODO: grab 'timezone' and store in 'location' > 'timezone' (if not already
    #   defined); note that it's not the same as utc_offset - utc_offset reflects
    #   daylight savings and thus is the true offset from UTC, whereas timezone
    #   does not change; e.g. an agust 5th fire in Florida is listed with timezone
    #   -5.0 and utc_offset (embedded in the 'date_time' field) '-04:00'

    ## 'date_time'
    OLD_DATE_TIME_MATCHER = re.compile('^(\d{12})(\d{2})?Z$')
    DATE_TIME_MATCHER = re.compile('^(\d{12})(\d{2})?([+-]\d{2}\:\d{2})$')
    DATE_TIME_FMT = "%Y%m%d%H%M"
    GROWTH_TIME_FORMAT = "%Y-%m-%dT%H:%M:%S"
    def _ingest_special_field_date_time(self, fire):
        """Ingests/parses 'date_time' field, found in sf2 fire data

        Note: older SF2 fire data formatted the date_time field without
        local timezone information, mis-representing everything as
        UTC.  E.g.:

            '201405290000Z'

        Newer (and current) SF2 fire data formats date_time like so:

            '201508040000-04:00'

        With true utc offset embedded in the string.
        """
        if not fire['location'].get('utc_offset') or not fire.get('growth'):
            date_time = self._parsed_input.get('date_time')
            if date_time:
                # this supports fires from bluesky daily runs;
                # 'date_time' is formatted like: '201508040000-04:00'
                try:
                    start = None
                    utc_offset = None
                    m = self.DATE_TIME_MATCHER.match(date_time)
                    if m:
                        start = datetime.datetime.strptime(
                            m.group(1), self.DATE_TIME_FMT)
                        utc_offset = m.group(3)
                    else:
                        m = self.OLD_DATE_TIME_MATCHER.match(date_time)
                        if m:
                            start = datetime.datetime.strptime(
                                m.group(1), self.DATE_TIME_FMT)
                            # Note: we don't know utc offset; don't set

                    if start is not None and not fire.get('growth'):
                        # As assume 24-hour
                        end = start + datetime.timedelta(hours=24)
                        # Note: this assumes time is local
                        fire['growth'] =[{
                            'start': start.strftime(self.GROWTH_TIME_FORMAT),
                            'end': end.strftime(self.GROWTH_TIME_FORMAT),
                            'pct': 100.0
                        }]

                    if utc_offset is not None and not fire['location'].get(
                            'utc_offset'):
                        fire['location']['utc_offset'] = utc_offset

                except Exception as e:
                    logging.warn("Failed to parse 'date_time' value %s",
                        date_time)



class FirePostProcessor(object):

    def __init__(self, fire):
        self._fire = fire

    ##
    ## Public Interface
    ##

    def process(self):
        self._process_growth_locations_and_fuelbeds()
        self._validate()

    ##
    ## Helper methods
    ##

    def _get_base_location(self, obj):
        if obj.get('location'):
            if obj['location'].get('geojson'):
                l = {'geojson': obj['location']['geojson']}
                if obj['location'].get('area'):
                    l['area'] = obj['location']['area']
                    return l
                elif obj['location']['geojson'].get('type') in GEOJSON_AREA_GEOMETRIES:
                    return l
                # other geometry types require area, so this is invalid
            # Note: at this point in the code, the following should always be
            # true (since FireIngester wouldn't have createdd the 'location'
            # object unless either the GeoJSON or lat+lng+area was defined)
            elif all([obj['location'].get(f) is not None for f in ('latitude', 'longitude', 'area')]):
                return {f: obj['location'][f] for f in ('latitude', 'longitude', 'area')}
        # else returns None

    def _copy_optional_location_fields(self, fire_location, growth_location):
        # This is different than the copying of the optional fields in
        # FireIngester in that, here, each field is copied over only if
        # it's not alredy defined in the growth's location
        if fire_location:
            for f in OPTIONAL_LOCATION_FIELDS:
                if f in fire_location and f not in growth_location:
                    growth_location[f] = fire_location[f]

    ##
    ## Processing
    ##

    def _process_growth_locations_and_fuelbeds(self):
        """Move location information from top level into growth objects.

        Makes sure either lat+lng+area or GeoJSON is defined either at the
        top level location or in each of the growh objects.

        TODO: restructure this method; maybe break up into multiple methods
        and encapsulate in a class
        """
        fire = self._fire
        top_level_base_location = self._get_base_location(fire)
        if fire.get('growth'):
            num_growth_objects = len(fire['growth'])
            if fire['location'].get('geojson') and num_growth_objects > 1:
                raise ValueError(IngestionErrMsgs.ONE_GEOJSON_MULTIPLE_GROWTH)

            for g in fire['growth']:
                g_pct = g.pop('pct', None)
                g_base_location = self._get_base_location(g)

                if (not not top_level_base_location) == (not not g_base_location):
                    raise ValueError(IngestionErrMsgs.BASE_LOCATION_AT_TOP_OR_PER_GROWTH)
                if not not fire.get('fuelbeds') and not not g.get('fuelbeds'):
                    raise ValueError(IngestionErrMsgs.FUELBEDS_AT_TOP_OR_PER_GROWTH)

                if top_level_base_location:
                    # initialize with base location; if it's a GeoJSON, then
                    # we know this is the only growth object given the check
                    # above; if it's lat+lng+area, we'll adjust the growth
                    # objets portion of the area
                    g['location'] = copy.deepcopy(top_level_base_location)
                    if fire['location'].get('area'):
                        # This must be the old, deprecated growth and location
                        # structure, so the growth object should either have
                        # 'pct' defined or be th eonly growth object
                        if not g_pct:
                            if num_growth_objects == 1:
                                g_pct = 100
                            else:
                                raise ValueError(
                                    IngestionErrMsgs.MULTIPLE_GROWTH_NO_PCT)
                        g['location']['area'] *= g_pct / 100.0

                    self._copy_optional_location_fields(fire['location'], g['location'])
                else:
                    # prune growth object's location so that it has the base
                    # location info plus optional fields
                    old_g_location = g.pop('location')
                    g['location'] = g_base_location
                    self._copy_optional_location_fields(old_g_location, g['location'])

                if fire.get('fuelbeds'):
                    # just copy over fuelbeds; there's no need to adjust
                    # percentages, since they apply to the growth's area (not
                    # the fire's total area), and we'll assume the same
                    # percentages for each growth object
                    g['fuelbeds'] = fire['fuelbeds']
                # else, whether or not fuelbeds are defined in the growth
                # object, do nothing (leave it as is if defined)
        else:
            if not top_level_base_location:
                raise ValueError(IngestionErrMsgs.NO_GROWTH_OR_BASE_LOCATION)
            fire['growth'] = [{
                'location': top_level_base_location
            }]
            self._copy_optional_location_fields(fire['location'],
                fire['growth'][0]['location'])
            if fire.get('fuelbeds'):
                fire['growth'][0]['fuelbeds'] = fire['fuelbeds']

        # delete top level location and fuelbeds, since each growth obejct
        # should have them now
        fire.pop('location', None)
        fire.pop('fuelbeds', None)

    ##
    ## Validation
    ##

    def _validate(self):
        # TODO: make sure required fields are all defined, and validate
        # values not validated by nested field specific _ingest_* methods
        self._validate_growth()

    def _validate_growth(self):
        """Provides extravalidation of growthinformation

        The ingest_ and process_ methods, above, already provide some
        validation
        """
        pass
