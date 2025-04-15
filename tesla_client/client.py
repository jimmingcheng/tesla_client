import requests


HOST = 'https://fleet-api.prd.na.vn.cloud.tesla.com'


class AuthenticationError(Exception):
    pass


class APIClient:
    access_token: str
    api_host: str

    def __init__(self, access_token: str, api_host: str = HOST) -> None:
        self.access_token = access_token
        self.api_host = api_host

    def api_get(self, endpoint: str) -> dict:
        resp = requests.get(
            self.api_host + endpoint,
            headers={
                'Authorization': 'Bearer ' + self.access_token,
                'Content-type': 'application/json',
            },
            verify=False,
        )

        try:
            resp.raise_for_status()
        except requests.HTTPError as ex:
            if ex.response.status_code in (401, 403):
                raise AuthenticationError
            else:
                raise

        return resp.json()

    def api_post(self, endpoint: str, json: dict | None = None) -> dict:
        resp = requests.post(
            self.api_host + endpoint,
            headers={
                'Authorization': 'Bearer ' + self.access_token,
                'Content-type': 'application/json',
            },
            json=json,
            verify=False,
        )

        try:
            resp.raise_for_status()
        except requests.HTTPError as ex:
            if ex.response.status_code in (401, 403):
                raise AuthenticationError
            else:
                raise

        try:
            return resp.json()
        except requests.exceptions.JSONDecodeError:
            return {'response': None}
