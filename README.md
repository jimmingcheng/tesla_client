# tesla_client

This library allows access to the unofficial Tesla API for reading data and issuing commands to Tesla vehicles.

## Quick Start

``` {.sourceCode .python}
import tesla_client


# Define an Account subclass of your own to provide an access_token
class MyTeslaAccount(tesla_client.Account):
    def get_access_token(self) -> str:
        return your_oauth_solution.get_up_to_date_access_token()


account = MyTeslaAccount()

# Access a vehicle in this account
vehicle = account.get_vehicles()[0]

# Fetch some data from the vehicle
vehicle.data_request('drive_state')

# Send a command to the vehicle
vehicle.command('honk_horn')
```

The Tesla API is not officially supported by Tesla, Inc. It may stop working at any time. For detailed documentation of API commands, see https://tesla-api.timdorr.com/. Thanks to Tim Dorr for his work in documenting the unofficial API.

Tesla, Inc. does not endorse or support this python library.

## Versions

### 4.0.2

- Relax python version requirement to 3.9

### 4.0.1

- Increase wait time for vehicle wake up
- Make sure navigation requests use direct API host instead of vcmd proxy

### 4.0.0

- Refactor with clearer and better typed interface for use by AI Agents

### 3.1.0

- Support Vehicle Command SDK

### 3.0.0

- Use official Tesla Fleet API

### 2.0.0

- Tesla removed support for grant_type=password. This version uses grant_type=authorization_code

### 1.0.0

- grant_type=password
