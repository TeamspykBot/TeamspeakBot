# TeamspeakBot ( WIP )

This is a teamspeak bot which provides all needed functionality to plugins
and can be extended endlessly by those. A MySQL server is currently required
to run this bot, as it stores its data there.

## TODO
- Add SQLite as an alternative to MySQL
- Provide separate callbacks for server query clients
- Add some still missing documentation inside internally used functions

## Bot Requirements
To use this Bot you must meet the following criteria:
- You are running python 3.4
- You are able to provide a MySQL Database for the Bot
- You have the package pymysql installed, as the Bot uses this MySQL driver

## Bot Setup
- Clone or download this repository
- Duplicate config.json.sample and name it config.json
- Fill in your values. You can find a complete explanation about the config [here](#)
- Import the sql dump into your database
- Run Main.py in the root directory

## How to develop plugins
Take a look at Bot/Plugins/Example.py which is a plugin implementing
every possible callback and event provided by the bot.
Otherwise head to the [develop documentation](doc/develop.md) for more
information about the event structure as well as possible caveats.

## Core contribution
To be written