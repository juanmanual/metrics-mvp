from datetime import datetime, time


class Prediction:
    def __init__(self, route_id: str, stop_id: str, prediction_dict: dict, queried_time: datetime):
        self.route_id = route_id
        self.stop_id = stop_id
        self.vehicle = prediction_dict['vehicle']
        self.predicted_minutes = prediction_dict['minutes']
        predicted_epoch_time = prediction_dict['epochTime']
        self.predicted_arrival_time = time.strftime(
            '%Y-%m-%d %H:%M:%S', time.localtime(predicted_epoch_time))
        self.queried_time = queried_time

    def get_predicted_arrival_time(self):
        return self.predicted_arrival_time

    def get_queried_time(self):
        return self.queried_time


class Predictions:
    def __init__(self, predictions: dict, route_id: str, stop_id: str, queried_time: datetime):
        # predictions is a mapping of direction tag to a list of Prediction items
        self.predictions = predictions
        self.route_id = route_id
        self.stop_id = stop_id
        self.queried_time = queried_time

    def get_predictions(self):
        return self.predictions
