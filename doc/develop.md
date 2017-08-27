# Introduction

Every plugin should be its own file in Bot/Plugins. The bot will load all classes which end with "Plugin". The file should import `BasePlugin` from `Bot.Plugins.Base` and the class should inherit the imported `BasePlugin`. Further, the class needs to provide a \_\_init\_\_ method which takes one argument, the `bot_instance` and calls the parents \_\_init\_\_ method with that argument. Most minimal plugin setup:

```Python
class MyFirstPlugin(BasePlugin):
    def __init__(self, bot_instance):
        super().__init__(bot_instance)
```

## Implementable functions



### on_initial_data
Arguments:
- client_list
- channel_list

Will be called everytime the bot logs into the teamspeak server. It will supply the initial list of clients and channel which are present at the given moment. See [data structures](#) for an overview about the structure of the arguments.


<br>
### on_client_joined
Arguments:
- event

Will be called everytime a client connects. See [data structures](#) for an overview about the structure of the arguments.


<br>
### on_client_left
Arguments:
- event

Will be called everytime a client disconnects. See [data structures](#) for an overview about the structure of the arguments.


<br>
### on_client_moved
Arguments:
- event

Will be called everytime a client moves between channels. See [data structures](#) for an overview about the structure of the arguments.


<br>
### on_private_text
Arguments:
- event

Will be called when te bot receives a private message. See [data structures](#) for an overview about the structure of the arguments.


<br>
### on_connection_lost

Will be called when the botr loses connection to the teamspeak server. The bot will try to reconnect and call on_initial_data as soon as a connection is established again.