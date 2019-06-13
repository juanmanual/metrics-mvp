import re
import requests
import json
import os
from xml.etree import ElementTree
from datetime import datetime

from models import predictions as p, nextbus, util
from . import util


def create_predictions_requests(agency_id: str) -> list:
    # TODO: error if response includes error

    # we can maximally split the string into num_routes/10 before the API complains that the URI is too long
    multi_stops = util.get_routes_to_stops_str(agency_id, 10)
    requests = []
    for stops in multi_stops:
        requests.append(
            f"http://webservices.nextbus.com/service/publicJSONFeed?command=predictionsForMultiStops&a={agency_id}{stops}")
    return requests


def get_prediction_data(agency_id: str):
    queried_time = datetime.now()
    if re.match(r'^[\w\-]+$', agency_id) is None:
        raise Exception(f"Invalid agency id: {agency_id}")

    # TODO: cache responses
    route_id_to_predictions = {}
    for request_url in create_predictions_requests(agency_id):
        response = requests.get(request_url)
        if response.status_code != 200:
            print(request_url)
            print(response.content)
            return

        route_id_to_predictions.update(
            parse_prediction_response(queried_time, response))
    return route_id_to_predictions


def parse_prediction_response(queried_time, resp):
    route_id_to_predictions = {}
    resp_json = resp.json()
    predictions_by_route = resp_json['predictions']
    for prediction_info in predictions_by_route:
        # print(prediction_info)
        route_id = prediction_info['routeTag']
        stop_id = prediction_info['stopTag']
        if 'direction' not in prediction_info:
            continue
        directions = prediction_info['direction']
        if isinstance(directions, list):
            # meaning there are multiple directions at this stop
            for direction in directions:
                predictions = direction['prediction']
                curr_map = gen_route_id_to_predictions(
                    route_id, stop_id, queried_time, predictions, route_id_to_predictions)
                route_id_to_predictions.update(curr_map)
        else:
            predictions = directions['prediction']
            curr_map = gen_route_id_to_predictions(
                route_id, stop_id, queried_time, predictions, route_id_to_predictions)
            route_id_to_predictions.update(curr_map)

    return route_id_to_predictions


def gen_route_id_to_predictions(route_id, stop_id: str, queried_time, predictions: list, route_id_to_predictions: dict):
    if isinstance(predictions, list):
        for prediction in predictions:
            new_prediction = gen_prediction(
                prediction, route_id, stop_id, queried_time)
            if route_id not in route_id_to_predictions:
                route_id_to_predictions[route_id] = []
            route_id_to_predictions[route_id].append(new_prediction)
    else:
        new_prediction = gen_prediction(
            predictions, route_id, stop_id, queried_time)
        if route_id not in route_id_to_predictions:
            route_id_to_predictions[route_id] = []
            route_id_to_predictions[route_id].append(new_prediction)
    return route_id_to_predictions


def gen_prediction(prediction, route_id, stop_id, queried_time):
    vehicle = prediction['vehicle']
    minutes = prediction['minutes']
    epoch_time = prediction['epochTime']
    dir_tag = prediction['dirTag']
    new_prediction = p.Prediction(
        route_id, stop_id, vehicle, minutes, epoch_time, queried_time, dir_tag)
    return new_prediction
