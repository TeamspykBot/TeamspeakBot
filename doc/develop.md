# Introduction

Every plugin should be its own file in Bot/Plugins. The bot will load all classes which end with "Plugin". The file should import `PluginBase` from `Bot.Plugins.Base` and the class should inherit the imported `PluginBase`. Further, the class needs to provide a `__init__` method which takes one argument, the `bot_instance` and calls the parents `__init__` method with that argument. Also, all your classes which are supposed to get loaded by the teamspeakbot need to end in `Plugin`. E.g `HelpPlugin` or `AutoKickPlugin`.

Most minimal plugin setup:

```Python
class MyFirstPlugin(PluginBase):
    def __init__(self, bot_instance):
        super().__init__(bot_instance)
```

## Implementable functions

### on_initial_data
Arguments:
- client_list
- channel_list

Will be called everytime the bot logs into the teamspeak server. It will supply the initial list of clients and channel which are present at the given moment. See [data structures](data-structures.md) for an overview about the structure of the arguments.

<br>

### on_client_joined
Arguments:
- event

Will be called everytime a client connects. See [data structures](data-structures.md) for an overview about the structure of the arguments.

<br>

### on_client_left
Arguments:
- event

Will be called everytime a client disconnects. See [data structures](data-structures.md) for an overview about the structure of the arguments.

<br>

### on_client_moved
Arguments:
- event

Will be called everytime a client moves between channels. See [data structures](data-structures.md) for an overview about the structure of the arguments.

<br>

### on_private_text
Arguments:
- event

Will be called when the bot receives a private message. See [data structures](data-structures.md) for an overview about the structure of the arguments.

<br>

### on_channel_text
Arguments:
- event

Will be called when the bot receives a channel message. Due to teamspeak server query limitations, this requires to have an active bot instance in every ( occupied )channel. As this drains many slots, this behaviour can be toggled in the settings. Please note that turning off that behaviour also means that this callback will never be called. See [data structures](data-structures.md) for an overview about the structure of the arguments.

<br>

### on_connection_lost
Arguments: None

Will be called when the bot loses connection to the teamspeak server. The bot will try to reconnect and call on_initial_data as soon as a connection is established again.

<br>

## Managing (persistent) data