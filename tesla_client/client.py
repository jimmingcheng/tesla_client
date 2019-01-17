import requests
import time
from collections import namedtuple


HOST = 'https://owner-api.teslamotors.com'


OAuthCredentials = namedtuple('OAuthCredentials', (
    'access_token',
    'refresh_token',
    'token_expiry',
))


_client_id = None
_client_secret = None


def init(client_id, client_secret):
    global _client_id, _client_secret
    _client_id = client_id
    _client_secret = client_secret


class APIClient():
    def get_access_token(self):
        raise NotImplementedError

    def api_get(self, endpoint):
        resp = requests.get(
            HOST + endpoint,
            headers={
                'Authorization': 'Bearer ' + self.get_access_token(),
                'Content-type': 'application/json',
            },
        )
        return resp.json()

    def api_post(self, endpoint, json=None):
        resp = requests.post(
            HOST + endpoint,
            headers={
                'Authorization': 'Bearer ' + self.get_access_token(),
                'Content-type': 'application/json',
            },
            json=json,
        )
        return resp.json()


class Account(APIClient):
    def get_credentials(self):
        raise NotImplementedError

    def save_credentials(self, creds):
        raise NotImplementedError

    def get_access_token(self):
        creds = self.get_credentials()
        if not creds.access_token or creds.token_expiry < time.time():
            new_creds = self.refresh_access_token(creds)
            self.save_credentials(new_creds)
            return new_creds.access_token
        else:
            return creds.access_token

    def refresh_access_token(self, creds):
        new_creds = requests.post(
            HOST + '/oauth/token',
            headers={
                'Content-type': 'application/json',
            },
            params={
                'client_id': _client_id,
                'client_secret': _client_secret,
                'grant_type': 'refresh_token',
                'refresh_token': creds.refresh_token,
            },
        ).json()

        return OAuthCredentials(
            access_token=new_creds['access_token'],
            refresh_token=new_creds['refresh_token'],
            token_expiry=new_creds['created_at'] + new_creds['expires_in'],
        )

    def login(self, email, password):
        creds = requests.post(
            HOST + '/oauth/token?grant_type=password',
            headers={
                'Content-type': 'application/json',
            },
            params={
                'grant_type': 'password',
                'client_id': _client_id,
                'client_secret': _client_secret,
                'email': email,
                'password': password,
            },
        ).json()

        self.save_credentials(
            OAuthCredentials(
                access_token=creds['access_token'],
                refresh_token=creds['refresh_token'],
                token_expiry=creds['created_at'] + creds['expires_in'],
            )
        )

    def get_vehicles(self):
        vehicles_json = self.api_get(
            '/api/1/vehicles'
        )['response']

        return [
            Vehicle(self, vehicle_json)
            for vehicle_json in vehicles_json
        ]


class Vehicle(APIClient):
    def __init__(self, account, vehicle_json):
        self.account = account
        self.id = vehicle_json['id']
        self.display_name = vehicle_json['display_name']

    def get_access_token(self):
        return self.account.get_access_token()

    def get_vehicle_data(self):
        return self.api_get(
            '/api/1/vehicles/{}/vehicle_data'.format(self.id)
        )['response']

    def wake_up(self):
        return self.api_post(
            '/api/1/vehicles/{}/wake_up'.format(self.id)
        )['response']

    def get_nearby_charging_sites(self):
        return self.api_get(
            '/api/1/vehicles/{}/nearby_charging_sites'.format(self.id)
        )['response']

    def data_request(self, resource):
        return self.api_get(
            '/api/1/vehicles/{}/data_request/{}'.format(self.id, resource)
        )['response']

    def command(self, command, json=None):
        return self.api_post(
            '/api/1/vehicles/{}/command/{}'.format(self.id, command),
            json=json,
        )['response']
