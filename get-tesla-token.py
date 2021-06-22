#!/usr/bin/env python3
import json
from getpass import getpass
from datetime import datetime, timedelta
import teslapy


def get_credentials(default_email):
    login = input('Enter your tesla.com login: [default={}]: '.format(default_email))
    if not login: 
        login = default_email
    else:
        login = login.strip()
    password = getpass('Please eneter password for {}: '.format(login))
    return (login, password)

    
def main():
    while True:
        try:
            (username, password) = get_credentials('anatoly.ivanov@gmail.com')
            with teslapy.Tesla(username, password) as client:
                client.fetch_token()
                while True:
                    validto = datetime.fromtimestamp(client.token['created_at']+client.token['expires_in'])
                    print(f'Token valid till: {validto}')
                    if validto > datetime.now() + timedelta(days=7):
                        break
                    print('Expires soon, refreshing token...')
                    client.refresh_token()

                print('"token": ', json.dumps(client.token, indent=4))
            break
        except KeyboardInterrupt as ex:
            print('Aborted')
            break
        except Exception as ex:
            print(f'this did not work: {ex.message}, let us try that again')



if __name__=='__main__':
    main()
