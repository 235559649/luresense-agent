"""Bounded Open-Meteo current-weather tool; no water-temperature inference."""
from datetime import datetime, timezone
import hashlib
import json
import math
from time import perf_counter
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler

ENDPOINT = 'https://api.open-meteo.com/v1/forecast'
FIELDS = {'temperature_2m': '°C', 'wind_speed_10m': 'km/h', 'precipitation': 'mm'}
LIMITATION = ('天气模型数据，不是现场实测；2米气温不是水温。'
              '降水是返回时间区间内的量，不是全天总量。不能据此推断鱼存在或中鱼率。')


class WeatherError(ValueError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def coordinates(latitude, longitude):
    values = []
    for value, low, high in ((latitude, -90, 90), (longitude, -180, 180)):
        if isinstance(value, bool):
            raise WeatherError('经纬度须为有限数字')
        try:
            number = float(value)
        except (TypeError, ValueError):
            raise WeatherError('请提供纬度和经度，不根据地名猜测位置') from None
        if not math.isfinite(number) or not low <= number <= high:
            raise WeatherError('纬度范围为 -90～90，经度范围为 -180～180')
        values.append(number)
    return tuple(values)


def transport(url):
    request = Request(url, headers={'User-Agent': 'LureSense-weather/1.0', 'Accept': 'application/json'})
    with build_opener(NoRedirect()).open(request, timeout=10) as response:
        raw = response.read(100001)
    if len(raw) > 100000:
        raise WeatherError('天气响应超过大小限制')
    return json.loads(raw)


def number(value):
    return type(value) in (int, float) and math.isfinite(value)


def normalize(payload, now):
    if not isinstance(payload, dict) or payload.get('error'):
        raise WeatherError('天气服务返回错误或无效结构')
    current, units = payload.get('current'), payload.get('current_units')
    if not isinstance(current, dict) or not isinstance(units, dict):
        raise WeatherError('天气响应缺少 current 或 current_units')
    timestamp = current.get('time')
    if units.get('time') != 'unixtime' or not number(timestamp):
        raise WeatherError('天气时间戳或单位无效')
    if not -1800 <= now.timestamp() - timestamp <= 10800:
        raise WeatherError('天气时间过旧或明显超前，未作为当前天气展示')
    interval = current.get('interval')
    if not number(interval) or interval <= 0 or units.get('interval') != 'seconds':
        raise WeatherError('天气数据时间区间无效')
    values = {}
    for name, unit in FIELDS.items():
        value = current.get(name)
        if units.get(name) != unit or not number(value):
            raise WeatherError('天气字段缺失或单位异常：' + name)
        if name != 'temperature_2m' and value < 0:
            raise WeatherError('风速或降水不能为负数')
        values[name] = {'value': value, 'unit': unit}
    lat, lon = coordinates(payload.get('latitude'), payload.get('longitude'))
    return dict(valid_at_utc=datetime.fromtimestamp(timestamp, timezone.utc).isoformat(),
                interval_seconds=interval, grid_location={'latitude': lat, 'longitude': lon},
                measurements=values)


def query_weather(latitude, longitude, mode='mock', fetch=None, now=None):
    if mode not in ('mock', 'live'):
        raise WeatherError('天气模式须为 mock 或 live')
    lat, lon = coordinates(latitude, longitude)
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise WeatherError('检查时间必须包含时区')
    url = ENDPOINT + '?' + urlencode(dict(latitude=lat, longitude=lon,
        current=','.join(FIELDS), temperature_unit='celsius', wind_speed_unit='kmh',
        precipitation_unit='mm', timezone='GMT', timeformat='unixtime', forecast_days=1))
    result = dict(tool='current_weather', mode=mode, synthetic=mode=='mock',
        status='error', request_attempted=False, response_received=False,
        requested_location={'latitude': lat, 'longitude': lon}, location_source='user_coordinates',
        retrieved_at_utc=now.isoformat(), source_url=url,
        attribution='Open-Meteo — https://open-meteo.com/',
        limitation=LIMITATION, water_temperature=None, data=None)
    start = perf_counter()
    try:
        if mode == 'mock':
            payload = dict(latitude=lat, longitude=lon,
                current={'time': int(now.timestamp()), 'interval': 900,
                         'temperature_2m': 25.0, 'wind_speed_10m': 8.0, 'precipitation': 0.0},
                current_units={'time': 'unixtime', 'interval': 'seconds', **FIELDS})
            result['attribution'] = '人工模拟样例；不是 Open-Meteo 实时返回'
        else:
            result['request_attempted'] = True
            payload = (fetch or transport)(url)
            result['response_received'] = True
        result['payload_sha256'] = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        result['provider_payload'] = payload
        result['data'] = normalize(payload, now)
        result['status'] = 'ok'
    except HTTPError as error:
        result['error'] = f'天气服务 HTTP {error.code}；未重试，未使用模拟值替代。'
    except (URLError, TimeoutError, OSError):
        result['error'] = '天气网络请求失败或超时；未重试，未使用模拟值替代。'
    except (ValueError, TypeError, KeyError, OverflowError):
        result['error'] = '天气响应未通过字段、单位或时效校验；未展示数值。'
    result['latency_seconds'] = round(perf_counter()-start, 4)
    return result


def render_weather(result):
    if result['status'] != 'ok':
        return '【天气工具失败】' + result['error']
    d = result['data'];m = d['measurements']
    lines = ['【模拟天气样例】' if result['synthetic'] else '【天气工具结果】',
        '请求坐标：' + str(result['requested_location']),
        '模型网格坐标：' + str(d['grid_location']),
        '数据时间（UTC）：' + d['valid_at_utc'],
        '数据区间（秒）：' + str(d['interval_seconds'])]
    for key, label in [('temperature_2m', '2米气温'), ('wind_speed_10m', '10米风速'), ('precipitation', '区间降水')]:
        lines.append(f"{label}：{m[key]['value']} {m[key]['unit']}")
    lines += [result['limitation'], result['attribution']]
    return '\n'.join(lines)
