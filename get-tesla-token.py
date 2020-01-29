#!/usr/bin/env python3
import asyncio
import json
from getpass import getpass
from tesla_api import TeslaApiClient

def get_credentials(default_email):
    login = input('Enter your tesla.com login: [default={}]: '.format(default_email))
    if not login: 
        login = default_email
    else:
        login = login.strip()
    password = getpass('Please eneter password for {}: '.format(login))
    return (login, password)

    
async def main():
    while True:
        try:
            (username, password) = get_credentials('anatoly.ivanov@gmail.com')
            client = TeslaApiClient(username, password)
            await client.authenticate()
            print('"token": ', json.dumps(client.token, indent=4))
            await client.close()
            break
        except:
            print('this did not work, let us ttry taht again')


if __name__=='__main__':
    asyncio.run(main())
