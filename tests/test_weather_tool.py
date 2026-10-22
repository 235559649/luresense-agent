from copy import deepcopy
from datetime import datetime, timezone
import unittest
from unittest.mock import Mock
from urllib.error import HTTPError, URLError
from weather_tool import coordinates, query_weather, normalize, WeatherError
from agent_tools import plan

NOW = datetime(2026, 10, 18, 10, tzinfo=timezone.utc)


def payload():
    return {'latitude':1.3,'longitude':103.8,
            'current':{'time':NOW.timestamp(),'interval':900,'temperature_2m':28.5,'wind_speed_10m':5.0,'precipitation':0.0},
            'current_units':{'time':'unixtime','interval':'seconds','temperature_2m':'°C','wind_speed_10m':'km/h','precipitation':'mm'}}


class WeatherTests(unittest.TestCase):
    def test_invalid_coordinates(self):
        for lat,lon in [(True,0),(float('nan'),0),(91,0),(0,181),(None,0)]:
            with self.subTest(lat=lat,lon=lon), self.assertRaises(WeatherError):coordinates(lat,lon)
        self.assertEqual(coordinates(0,0),(0,0))

    def test_mock_never_requests(self):
        fetch=Mock(side_effect=AssertionError('network'))
        r=query_weather(0,0,fetch=fetch,now=NOW)
        self.assertTrue(r['synthetic']);self.assertFalse(r['request_attempted'])
        self.assertEqual(r['status'],'ok');fetch.assert_not_called()

    def test_live_records_provenance_and_units(self):
        fetch=Mock(return_value=payload())
        r=query_weather(1.31,103.81,'live',fetch,NOW)
        self.assertEqual(r['status'],'ok');self.assertFalse(r['synthetic'])
        self.assertTrue(r['response_received']);self.assertIsNone(r['water_temperature'])
        self.assertNotEqual(r['requested_location'],r['data']['grid_location'])
        fetch.assert_called_once();self.assertIn('timeformat=unixtime',fetch.call_args.args[0])

    def test_timeout_no_fake_data_no_retry(self):
        fetch=Mock(side_effect=TimeoutError())
        r=query_weather(1,2,'live',fetch,NOW)
        self.assertEqual(r['status'],'error');self.assertIsNone(r['data'])
        self.assertFalse(r['synthetic']);fetch.assert_called_once()

    def test_http_error_no_body_leak(self):
        fetch=Mock(side_effect=HTTPError('url',429,'sensitive',{},None))
        r=query_weather(1,2,'live',fetch,NOW)
        self.assertIn('429',r['error']);self.assertNotIn('sensitive',r['error'])

    def test_missing_measurement(self):
        p=payload();p['current']['temperature_2m']=None
        r=query_weather(1,2,'live',lambda _:p,NOW)
        self.assertEqual(r['status'],'error');self.assertIsNone(r['data'])

    def test_wrong_unit(self):
        p=payload();p['current_units']['wind_speed_10m']='m/s'
        with self.assertRaises(WeatherError):normalize(p,NOW)

    def test_stale_and_future(self):
        for shift in [-20000,4000]:
            p=payload();p['current']['time']+=shift
            with self.subTest(shift=shift),self.assertRaises(WeatherError):normalize(p,NOW)

    def test_nonfinite_and_negative(self):
        for field,value in [('temperature_2m',float('inf')),('precipitation',-1),('wind_speed_10m',True)]:
            p=payload();p['current'][field]=value
            with self.subTest(field=field),self.assertRaises(WeatherError):normalize(p,NOW)

    def test_provider_error(self):
        r=query_weather(1,2,'live',lambda _:{'error':True},NOW)
        self.assertEqual(r['status'],'error')

    def test_diet_does_not_query_weather(self):
        self.assertEqual(plan('大口黑鲈吃什么？')['weather'],False)

    def test_temperature_concept_does_not_query(self):
        self.assertFalse(plan('今天的气温能代替水温吗？')['weather'])

    def test_current_weather_routes(self):
        p=plan('查询当前天气和风速')
        self.assertTrue(p['weather']);self.assertFalse(p['knowledge'])

    def test_future_is_not_current(self):
        p=plan('查询明天天气')
        self.assertFalse(p['weather']);self.assertFalse(p['knowledge'])

    def test_combined_routes(self):
        p=plan('今天的天气如何？我在湖泊看到倒木，应该先看哪里？')
        self.assertTrue(p['weather']);self.assertTrue(p['knowledge'])

    def test_explicit_flag(self):
        self.assertTrue(plan('我在湖泊看到倒木，应该先看哪里？',True)['weather'])


if __name__=='__main__':unittest.main()
