
from . import util, nextbus
import pandas as pd
import numpy as np
import re
import json

places = {
    'pier39': (37.8081969,-122.4109649),
    'ggp_s': (37.7646285,-122.4805198),
    'civic': (37.7794374,-122.4173052),
    'nobhill': (37.794410,-122.417540),
    'cfa': (37.781710,-122.408360),
    'excelsior': (37.7256702,-122.4266506),
    'zoo': (37.7354229,-122.5052357),
    'sutrobaths': (37.7797535,-122.5099845),
    'ftmason': (37.8044515,-122.4256411),
    'ferrybldg': (37.7949803,-122.3941556),
    'citycollege': (37.7265988,-122.4515044),
    'missiondolores': (37.7600258,-122.4274505),
    'hunterspoint': (37.7292118,-122.3710202),
    'tankhill': (37.7590492,-122.4475806),
    'castro': (37.7622384,-122.4337082),
}

def get_lat_lon(place):
    if ',' in place:
        parts = place.split(',')
        return (float(parts[0]), float(parts[1]))
    else:
        return places[place]

transfers_version = 't1'

def get_transfers_cache_path(agency_id: str):
    if re.match('^[\w\-]+$', agency_id) is None:
        raise Exception(f"Invalid agency: {agency_id}")

    data_dir = util.get_data_dir()
    return f'{data_dir}/transfers_{transfers_version}_{agency_id}.csv'

trip_times_version = 't1'

def get_trip_times_cache_path(agency_id: str):
    if re.match('^[\w\-]+$', agency_id) is None:
        raise Exception(f"Invalid agency: {agency_id}")

    data_dir = util.get_data_dir()
    return f'{data_dir}/trip_times_{trip_times_version}_{agency_id}.json'

wait_times_version = 't1'

def get_wait_times_cache_path(agency_id: str):
    if re.match('^[\w\-]+$', agency_id) is None:
        raise Exception(f"Invalid agency: {agency_id}")

    data_dir = util.get_data_dir()
    return f'{data_dir}/wait_times_{wait_times_version}_{agency_id}.json'

def get_nearby_stops(locations, lat_lon, max_dist=600):

    lat = lat_lon[0]
    lon = lat_lon[1]

    loc_df = locations.get_data_frame().copy()

    loc_df['DIST'] = util.haver_distance(loc_df['LAT'], loc_df['LON'], lat, lon)

    nearby = loc_df[loc_df['DIST'] < max_dist]
    nearby = nearby.sort_values('DIST')

    seen_directions = {}
    data = []

    for row in nearby.itertuples():
        loc = locations.get_location_by_id(row.LOCATION_ID)
        for s in loc.stop_infos:
            direction_ids = s.route.get_directions_for_stop(s.id)
            for did in direction_ids:
                if did not in seen_directions:
                    index = s.route.get_direction_info(did).get_stop_ids().index(s.id)
                    data.append((row.DIST, s.id, s.route.id, did, index, loc.id, s))
                    seen_directions[did] = True

    return pd.DataFrame(data, columns=['DIST', 'SID', 'ROUTE', 'DID', 'DIR_INDEX', 'LOCATION_ID', 'STOP_INFO'])

class CachedTripTimes:
    def __init__(self, trip_times_map):
        self.trip_times_map = trip_times_map

    def get_average(self, did, dir_index_a, dir_index_b):
        if did in self.trip_times_map:
            dir_trip_times = self.trip_times_map[did]
            if len(dir_trip_times) > dir_index_b:
                time_b = dir_trip_times[dir_index_b]
                time_a = dir_trip_times[dir_index_a]
                if time_b is not None and time_a is not None:
                    trip_time = time_b - time_a
                    if trip_time <= 0:
                        return np.nan # bad data
                    return trip_time
                else:
                    return np.nan
        else:
            return np.nan

class CachedWaitTimes:
    def __init__(self, wait_times_map):
        self.wait_times_map = wait_times_map

    def get_average(self, did, stop_id):
        if did in self.wait_times_map:
            dir_trip_times = self.wait_times_map[did]
            if stop_id in dir_trip_times and dir_trip_times[stop_id] is not None:
                return dir_trip_times[stop_id]
        return np.nan


def get_cached_trip_times(agency_id):
    with open(get_trip_times_cache_path(agency_id), 'r') as f:
        return CachedTripTimes(json.loads(f.read()))

def get_cached_wait_times(agency_id):
    with open(get_wait_times_cache_path(agency_id), 'r') as f:
        return CachedWaitTimes(json.loads(f.read()))

def get_possible_trips(locations, start_lat_lon, end_lat_lon, direct=False, max_walk=600):

    start_stops = get_nearby_stops(locations, start_lat_lon, max_walk)
    end_stops = get_nearby_stops(locations, end_lat_lon, max_walk)

    cached_trip_times = get_cached_trip_times(locations.agency_id)
    cached_wait_times = get_cached_wait_times(locations.agency_id)

    direct_trips = start_stops.merge(end_stops, how='inner', on='DID', suffixes=('_1','_2'))
    direct_trips = direct_trips[direct_trips['DIR_INDEX_1'] < direct_trips['DIR_INDEX_2']]
    direct_trips['WALK_DIST'] = (direct_trips['DIST_1'] + direct_trips['DIST_2']).round(1)
    direct_trips = direct_trips[direct_trips['WALK_DIST'] <= max_walk]

    if direct_trips.empty:
        direct_trips["BUS_MIN"] = np.nan
    else:
        direct_trips["BUS_MIN"] = direct_trips.apply(lambda row: cached_trip_times.get_average(row.DID, row.DIR_INDEX_1, row.DIR_INDEX_2), axis=1)

    direct_trips = direct_trips[direct_trips['BUS_MIN'].notnull()]

    walk_meters_per_minute = walk_speed * 60 # meters per minute

    direct_trips["WALK_MIN"] = (direct_trips["WALK_DIST"] / walk_meters_per_minute).round(1)
    direct_trips["TRIP_MIN"] = direct_trips["BUS_MIN"] + direct_trips["WALK_MIN"]
    direct_trips = direct_trips.rename({'DID':'DID_1'}, axis=1)
    direct_trips['ROUTE_2'] = direct_trips['ROUTE_1']
    direct_trips['DID_2'] = direct_trips['DID_1']
    direct_trips = direct_trips[['TRIP_MIN','BUS_MIN','WALK_MIN','WALK_DIST','ROUTE_1','DID_1','SID_1','ROUTE_2','DID_2','SID_2']]

    if direct:
        direct_trips = direct_trips.sort_values('TRIP_MIN').reset_index(drop=True)
        return direct_trips
    else:
        direct_routes = direct_trips['ROUTE_1'].unique()

        if len(direct_routes) > 0:
            # skip transfers if we have a direct trip with that route
            s1 = start_stops[~start_stops['ROUTE'].isin(direct_routes)]
            e1 = end_stops[~end_stops['ROUTE'].isin(direct_routes)]
        else:
            s1 = start_stops
            e1 = end_stops

        s1 = s1.copy()
        s1['X'] = 1 # add series with same value on all rows so pandas can calculate cross product
        e1 = e1.copy()
        e1['X'] = 1

        start_end_stops = s1.merge(e1, how='outer', on='X', suffixes=('_1','_2'))

        start_end_stops = start_end_stops[start_end_stops['DIST_1'] + start_end_stops['DIST_2'] <= max_walk]

        transfers = pd.read_csv(get_transfers_cache_path(locations.agency_id), dtype={'SID_1':str,'SID_2':str,'ROUTE_1':str,'ROUTE_2':str})
        transfers = transfers.drop(['ROUTE_1','ROUTE_2'], axis=1)

        transfer_trips = start_end_stops.merge(transfers, how='inner', on=['DID_1','DID_2'], suffixes=('_A','_B'))

        transfer_trips = transfer_trips[(transfer_trips['DIR_INDEX_1_A'] < transfer_trips['DIR_INDEX_1_B']) & (transfer_trips['DIR_INDEX_2_B'] < transfer_trips['DIR_INDEX_2_A'])]

        transfer_trips['WALK_DIST'] = (transfer_trips['DIST_1'] + transfer_trips['DIST_2'] + transfer_trips['TRANSFER_DIST']).round(1)
        transfer_trips["WALK_MIN"] = (transfer_trips["WALK_DIST"] / walk_meters_per_minute).round(1)

        transfer_trips = transfer_trips[transfer_trips['WALK_DIST'] <= max_walk]

        transfer_trips = transfer_trips.rename({
            'SID_1_A': 'SID_1',
            'SID_2_A': 'SID_2',
            'SID_1_B': 'XFER_SID_1',
            'SID_2_B': 'XFER_SID_2'
        }, axis=1)

        if transfer_trips.empty:
            transfer_trips["XFER_MIN"] = np.nan
            transfer_trips["BUS_MIN_1"] = np.nan
            transfer_trips["BUS_MIN_2"] = np.nan
        else:
            transfer_trips["XFER_MIN"] = transfer_trips.apply(lambda row: cached_wait_times.get_average(row.DID_2, row.XFER_SID_2), axis=1)
            transfer_trips["BUS_MIN_1"] = transfer_trips.apply(lambda row: cached_trip_times.get_average(row.DID_1, row.DIR_INDEX_1_A, row.DIR_INDEX_1_B), axis=1)
            transfer_trips["BUS_MIN_2"] = transfer_trips.apply(lambda row: cached_trip_times.get_average(row.DID_2, row.DIR_INDEX_2_B, row.DIR_INDEX_2_A), axis=1)

        transfer_trips["BUS_MIN"] = transfer_trips["BUS_MIN_1"] + transfer_trips["BUS_MIN_2"]

        transfer_trips = transfer_trips[transfer_trips['BUS_MIN'].notnull()]

        transfer_trips["TRIP_MIN"] = transfer_trips["BUS_MIN"] + transfer_trips["WALK_MIN"] + transfer_trips["XFER_MIN"]

        #transfer_trips.to_csv('transfers.csv', index=False)

        all_trips = pd.concat([direct_trips, transfer_trips], sort=False)
        all_trips = all_trips.sort_values('TRIP_MIN').reset_index(drop=True)

        return all_trips[['TRIP_MIN','BUS_MIN','WALK_MIN','XFER_MIN','WALK_DIST','ROUTE_1','DID_1','SID_1','XFER_SID_1','ROUTE_2','DID_2','XFER_SID_2','SID_2']]
