## Introduction

You can customize your teamspeakbot instance by changing values inside your config.json.
The root in your config.json holds two or more keys. First, you can declare a
config namespace with they key `config_namespace`. The bot will now search
a key in the root level which equals the value the namespace. That way, you can keep
multiple configs in one file and easily swap them out. Inside your namespace you can have the following values:


- bot_name: Sets the name of the main bot. The bot will try to set his name as soon as he connect.
In the future there will also be the possibility to handle the situation when the botname is already taken

- command_prefix: Every command needs to be prefixed with the given string here. E.g if the command is
subscribe and the command_prefix is a dot, the command needs to be .subscribe

- channel_text: Enables the possibility to track text messages in every channel. This comes with a caveat
due to teamspeak limitations: Every channel with one or more clients needs to have a serverquery client in it,
thus occupying many slots.

- load_all_plugins: When this is set to true, the bot will load all plugins which are in Bot/Plugins.
Otherwise only plugins specified in plugin_list will be loaded.

- plugin_list: A list of strings with plugin names to load. Only needed when `load_all_plugins` is false.
E.g `["AFKSwitcher", "YoutubePlugin"]`. You need to input the actual file names without an extension.

- mysql: Groups mysql connection information
    - host: domain or IP to connect to
    - port: port ( when in doubt, set it to 3306 as its the default port)
    - user: mysql user
    - password: mysql password
    - db: db to use, you need to have imported the sql dump there

- serverquery
    - host: domain or IP to connect to
    - port: port ( when in doubt, set it to 10011 as its the default port)
    - user: serverquery user
    - password: serverquery password
    - virtualserverid: virtual ID of that server. Usually 1 if you only have one virtual server running.

- accesslevel: Configure accesslevel for your servergroups here
    - default: The default accesslevel. When in doubt set to 0.
    - groups: You can add servergroups and their accesslevel here.

- plugins: Move plugin specific configuration here. Every plugin is encouraged
to make them as configurable as possible. Plugins are supposed to have atleast
a class docstring explaining possible commands and config values as well as
show an example config.

Example Config:

```
{
    "config_namespace": "development",
    "development": {
        "bot_name": "Bot",
        "command_prefix": ".",
        "channel_text": true,
        "load_all_plugins": true,
        "plugin_list": [],
        "mysql": {
            "host": "localhost",
            "port": 3306,
            "user": "ts3bot",
            "password": "root",
            "db": "ts3bot"
        },
        "serverquery": {
            "host": "127.0.0.1",
            "port": 10011,
            "user": "serveradmin",
            "password": "pass",
            "virtualserverid": 1
        },
        "accesslevel": {
            "default": 0,
            "groups": {
                "Server Admin": 10,
                "Normal": 1
            }
        },
        "plugins": {
            "mydayyy_link_distribution": {
                "commands": {
                    "link_subscribe": {
                        "accesslevel": 0,
                        "command": "linkSubscribe"
                    }
                },
                "table_name1": "LinkDistribution",
                "table_name2": "LinkDistribution_Clients"
            },
            "kleest": {
                "yt": {
                    "api_key": "AIzaSyBoF3gSI5z4HYBiWYtKRB2WTrQ0AaI5Jao"
                },
                "afk": {
                    "cid": 29,
                    "timeout": 10000
                }
            }
        }
    }
}
```