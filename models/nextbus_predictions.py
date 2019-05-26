import re
import requests
import json
import os
from xml.etree import ElementTree
from datetime import datetime

from models import predictions as p
from . import util


def get_prediction_data(agency_id: str, route_id: str, stop_id: str) -> p.Predictions:
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
