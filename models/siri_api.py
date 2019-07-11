import requests
import json

from . import predictions as p


def get_all_predictions(api_key: str, agency: str) -> dict:
    url = f"http://api.511.org/transit/StopMonitoring?api_key={api_key}&agency={agency}"
    resp = requests.get(url)
    if resp.status_code != 200:
        resp.raise_for_status()
    resp.encoding = 'utf-8-sig'
    resp_json = resp.json()
    all_predictions = resp_json['ServiceDelivery']['StopMonitoringDelivery']['MonitoredStopVisit']
    queried_time = resp_json['ServiceDelivery']['ResponseTimestamp']
    # predictions_obj = p.Predictions(queried_time, agency)
    stops_to_predictions = {}
    for prediction in all_predictions:
        prediction_data = parse_prediction_return(prediction)
        prediction_data['agency'] = agency
        new_prediction = p.Prediction.from_data(prediction_data)
        stop_id = new_prediction.stop_id
        if stop_id not in stops_to_predictions:
            stops_to_predictions[stop_id] = p.PredictionsByStop(
                stop_id, queried_time, [], agency)
        stops_to_predictions[stop_id].add_prediction(new_prediction)
    return stops_to_predictions


def get_predictions_by_stop_id(api_key: str, agency: str, stop_id: str):
    url = f"http://api.511.org/transit/StopMonitoring?api_key={api_key}&agency={agency}&stopCode={stop_id}"
    resp = requests.get(url)
    if resp.status_code != 200:
        resp.raise_for_status()
    resp.encoding = 'utf-8-sig'
    resp_json = resp.json()
    all_predictions = resp_json['ServiceDelivery']['StopMonitoringDelivery']['MonitoredStopVisit']
    queried_time = resp_json['ServiceDelivery']['ResponseTimestamp']
    predictions = []
    for pred in all_predictions:
        pred_data = parse_prediction_return(pred)
        pred_data['agency'] = agency
        prediction = p.Prediction.from_data(pred_data)
        predictions.append(prediction)
    predictions_by_stop = p.PredictionsByStop(
        stop_id, queried_time, predictions, agency)
    return predictions_by_stop


def parse_prediction_return(prediction: dict) -> dict:
    return {
        'queried_time': prediction['RecordedAtTime'],
        'route_id': prediction['MonitoredVehicleJourney']['LineRef'],
        'stop_id': prediction['MonitoredVehicleJourney']['MonitoredCall']['StopPointRef'],
        'trip_id': prediction['MonitoredVehicleJourney']['FramedVehicleJourneyRef']['DatedVehicleJourneyRef'],
        'arrival_time': prediction['MonitoredVehicleJourney']['MonitoredCall']['AimedArrivalTime'],
        'direction': prediction['MonitoredVehicleJourney']['DirectionRef'],
    }