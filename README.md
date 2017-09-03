# TeamspeakBot ( WIP )

This is a teamspeak bot which provides all needed functionality to plugins and can be extended endlessly by those. A MySQL server is currently required to run this bot, as it stores its data there.

## TODO
- Add SQLite as an alternative to MySQL
- Provide separate callbacks for server query clients
- Add some still missing documentation inside internally used functions

## How to develop plugins
Take a look at Bot/Plugins/Example.py which is a plugin implementing every possible callback and event provided by the bot. Otherwise head to the [develop documentation](doc/develop.md) for more information about the event structure as well as possible caveats.

## Core contribution
To be written