from health.services import calculate_airworthiness


class AirworthinessMixin:
    def get_airworthiness(self, obj):
        return calculate_airworthiness(obj).to_dict()
