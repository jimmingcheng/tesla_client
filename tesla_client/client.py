from typing import TYPE_CHECKING
import requests
from requests.models import Response


if TYPE_CHECKING:
    from tesla_client.account import Account


HOST = 'https://fleet-api.prd.na.vn.cloud.tesla.com'


class AuthenticationError(Exception):
    pass


class VehicleAsleepError(Exception):
    pass


class APIClient:
    account: 'Account'
    access_token: str
    api_host: str

    def __init__(self, account: 'Account', api_host: str = HOST) -> None:
        self.account = account
        self.api_host = api_host
        self.access_token = self.account.get_fresh_access_token()

    def api_get(self, endpoint: str, is_retry: bool = False) -> Response:
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
                if is_retry:
                    raise AuthenticationError
                else:
                    self.access_token = self.account.get_fresh_access_token()
                    return self.api_get(endpoint, is_retry=True)
            elif ex.response.status_code == 408:
                raise VehicleAsleepError
            else:
                raise

        return resp

    def api_post(
        self,
        endpoint: str,
        is_retry: bool = False,
        json: dict | None = None,
        host_override: str | None = None,
    ) -> Response:
        host = host_override or self.api_host

        resp = requests.post(
            host + endpoint,
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
                if is_retry:
                    raise AuthenticationError
                else:
                    self.access_token = self.account.get_fresh_access_token()
                    return self.api_post(endpoint, is_retry=True, json=json)
            elif ex.response.status_code in (408, 500):
                raise VehicleAsleepError
            else:
                raise

        return resp

    def api_delete(
        self,
        endpoint: str,
    ) -> Response:
        resp = requests.delete(
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
            elif ex.response.status_code in (408, 500):
                raise VehicleAsleepError
            else:
                raise

        return resp
