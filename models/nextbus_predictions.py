import re
import requests
import json
import os
from xml.etree import ElementTree
from datetime import datetime

from models import predictions as p, nextbus
from . import util

STOPS_STR = '&stops='


def generate_all_stops(agency_id: str) -> str:
    route_infos = nextbus.get_route_list(agency_id)
    route_ids = map(lambda route_info: route_info.id, route_infos)
    route_id_to_stop_ids = {}
    for route_id in route_ids:
        route_config = nextbus.get_route_config(agency_id, route_id)
        route_id_to_stop_ids[route_id] = route_config.get_stop_ids()

    all_stops = STOPS_STR
    for route, stop_ids in route_id_to_stop_ids.items():
        stops = [f"{route}|{stop_id}" for stop_id in stop_ids]
        all_stops += STOPS_STR.join(stops)
    return f"{STOPS_STR}{all_stops}"


def get_prediction_data(agency_id: str, route_id: str, stop_id: str):
    queried_time = datetime.Now()
    if re.match(r'^[\w\-]+$', agency_id) is None:
        raise Exception(f"Invalid agency id: {agency_id}")

    cache_path = os.path.join(
        util.get_data_dir(), f"prediction_{agency_id}_{route_id}_{stop_id}.json")

    response = requests.get(
        f"http://webservices.nextbus.com/service/publicXMLFeed?command=predictions&a={agency_id}&r={route_id}&s={stop_id}")

    # TODO: error if response includes error
    root = ElementTree.fromstring(response.content)
    root_predictions = root.find('predictions')
    directions = root_predictions.findall('directions')
    all_predictions = {}
    for direction in directions:
        predictions = direction.findall('prediction')
        for p in predictions:
            p_vals = p.attrib
            dirTag = p_vals[dirTag]
            if dirTag not in all_predictions:
                all_predictions[dirTag] = []
            curr_prediction = p.Prediction(
                route_id, stop_id, p_vals, queried_time)
            all_predictions[dirTag].append(curr_prediction)
    return p.Predictions(
        all_predictions, route_id, stop_id, queried_time)
