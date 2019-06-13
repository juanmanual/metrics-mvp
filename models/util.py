from datetime import datetime, date, timedelta
import os
import pytz
from models import nextbus

STOPS_STR = '&stops='


def parse_date(date_str):
    (y, m, d) = date_str.split('-')
    return date(int(y), int(m), int(d))

# todo: allow specifying day(s) of week


def get_dates_in_range(start_date_str, end_date_str, max_dates=1000):
    start_date = parse_date(start_date_str)
    end_date = parse_date(end_date_str)

    delta = end_date - start_date
    if delta.days < 0:
        raise Exception(f'start date after end date')

    incr = timedelta(days=1)

    res = []
    cur_date = start_date
    while True:
        res.append(cur_date)
        cur_date = cur_date + incr
        if cur_date > end_date:
            break

        if len(res) > max_dates:
            raise Exception(
                f'too many dates between {start_date_str} and {end_date_str}')

    return res


def render_dwell_time(seconds):
    # remove 0 hours and replace 00 minutes with spaces to make it easier to scan column for large durations
    return f'+{timedelta(seconds=round(seconds))}'.replace('+0:', '+').replace('+00:', '+  :')


def get_data_dir():
    return f"{os.path.dirname(os.path.dirname(os.path.realpath(__file__)))}/data"

def get_timestamp_or_none(d: date, time_str: str, tz: pytz.timezone):
    return int(get_localized_datetime(d, time_str, tz).timestamp()) if time_str is not None else None

def get_localized_datetime(d: date, time_str: str, tz: pytz.timezone):

    time_str_parts = time_str.split('+')  # + number of days

    if len(time_str_parts[0].split(':')) == 2:
        format = "%Y-%m-%d %H:%M"
    else:
        format = "%Y-%m-%d %H:%M:%S"

    dt_str = f"{d.isoformat()} {time_str_parts[0]}"

    dt = datetime.strptime(dt_str, format)
    if len(time_str_parts) > 1:
        dt = dt + timedelta(days=int(time_str_parts[1]))

    return tz.localize(dt)


'''
Generate a list of strings in the format '&stops={route_id}|{stop_id}...'
Since we can't substitute every stop on every route into an api call at once,
segment the number of strings created by num_routes_per_str
'''


def get_routes_to_stops_str(agency_id: str, num_routes_per_str: int) -> str:
    route_ids = [route.id for route in nextbus.get_route_list(agency_id)]
    route_id_to_stop_ids = {}
    for route_id in route_ids:
        route_config = nextbus.get_route_config(agency_id, route_id)
        route_id_to_stop_ids[route_id] = route_config.get_stop_ids()

    route_strs = []
    num_routes = len(route_ids)
    for route_idx in range(0, num_routes, num_routes_per_str):
        route_str = ''
        for tmp_route_idx in range(route_idx, route_idx + num_routes_per_str-1):
            if tmp_route_idx == num_routes:
                break
            route_id = route_ids[tmp_route_idx]
            route_str += gen_stop_str_for_route(
                route_id, route_id_to_stop_ids[route_id])
        route_strs.append(route_str)
    return route_strs


def gen_stop_str_for_route(route_id: str, stop_ids: list) -> str:
    all_stops = STOPS_STR
    stops = [f"{route_id}|{stop_id}" for stop_id in stop_ids]
    all_stops += STOPS_STR.join(stops)
    return all_stops
