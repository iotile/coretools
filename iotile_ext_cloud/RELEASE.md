# Release Notes

All major changes in each released version of the iotile-ext-cloud plugin are listed here.

## 0.3.1

- Start adding common utility functions

## 0.3.0

- Add the ability to autologin to iotile.cloud if the user is in an interactive session
  and they don't have stored cloud credentials.  We will prompt for a username/password
  on the command line.

## 0.2.3

- Modified device lookup to conditionally filter by project or not

## 0.2.2

- Fix jwt token refresh to work on non default iotile.cloud servers.

## 0.2.1

- Add cloud:server config variable for configuring different domains for talking to iotile.cloud.
  This allows for dev, test and staging servers to be setup and CoreTools pointed at them.

## 0.2.0

- Rename exceptions for better compatibility

## 0.1.1

- Improved documentation

## 0.1.0

- Initial public release