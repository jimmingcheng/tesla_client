# tesla_client

This library allows access to the unofficial Tesla API for reading data and issuing commands to Tesla vehicles.

A key feature of this library is that it offers an easy way to sync OAuth credentials with a data store of your choice. Credentials are auto-saved on login, or during token refreshes.

## Quick Start

``` {.sourceCode .python}
import tesla_client

tesla_client.init(CLIENT_ID, CLIENT_SECRET)  # Get these values from https://pastebin.com/pS7Z6yyP

# Define an Account subclass of your own to manage OAuth credential storage
class MyTeslaAccount(tesla_client.Account):
    def get_credentials(self):
        return your_credentials_store.get()

    def save_credentials(self, creds):
        your_credentials_store.save(creds)


account = MyTeslaAccount()

# Log in (and automatically save the OAuth credentials)
account.login('mrsteven@gmail.com', 'password')

# Access a vehicle in this account
vehicle = account.get_vehicles()[0]

# Fetch some data from the vehicle
vehicle.data_request('drive_state')

# Send a command to the vehicle
vehicle.command('honk_horn')
```

The Tesla API is not officially supported by Tesla, Inc. It may stop working at any time. For detailed documentation of API commands, see https://tesla-api.timdorr.com/. Thanks to Tim Dorr for his work in documenting the unofficial API.

Tesla, Inc. does not endorse or support this python library.
