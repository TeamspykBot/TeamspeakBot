# coding=utf-8
import inspect
from enum import Enum
import socket

import Network
import Bot.MysqlManager
import Bot.QueryManager
import Bot.DataManager
import importlib
import os

from Bot.Utility import starts_with_c_i, normalize_message, Event, escape, Timer, ChatCommand

from Globals import config, environment

eventTypes = Enum("EventTypes", "CLIENT_JOINED "
                                "CLIENT_LEFT "
                                "CLIENT_MOVED "
                                "PRIVATE_TEXT "
                                "LOST_CONNECTION ")


class TeamspeakBot:
    def __init__(self, ip, port=10011, user=None, password=None, virtual_server_id=None):
        """!
        @brief Constructs a TeamspeakBot instance

        @param ip Ip of the server you want to connect to
        @param port Port of the server yoú want to connect to
        @param user Serverquery username
        @param password Serverquery password
        @param virtual_server_id The virtual id of the serverr you want the bot to manage
        """

        self._conn = None

        self._init_networking(ip, port)
        self._ip = ip
        self._port = port

        self._user = user
        self._password = password
        self._virtualServerId = virtual_server_id

        self._mysqlManager = Bot.MysqlManager.MysqlManager()
        self._mysqlManager.connect_to_d_b(config.get_value(environment + ".mysql.host"),
                                          config.get_value(environment + ".mysql.port"),
                                          config.get_value(environment + ".mysql.user"),
                                          config.get_value(environment + ".mysql.password"),
                                          config.get_value(environment + ".mysql.db"))

        self._dataManager = Bot.DataManager.DataManager(self._mysqlManager)
        self._dataManager.set_default_access_level(config.get_value(environment + ".accesslevel.default"))
        self._dataManager.set_access_levels(config.get_value(environment + ".accesslevel.groups"))

        self._timer = Timer()
        self._timer.start_timer(self._update_all_clients, 250, False)
        self._timer.start_timer(self._update_all_client_servergroups, 250, False)

        self._queryTracker = Bot.QueryManager.QueryTracker()

        self._callbacksValueChanged = {}
        self._chatCommands = {}

        self._pluginList = []
        self._setup_plugins()

        self._lastLine = ""

    def _setup_plugins(self):
        """!
        @brief initializes all plugins which are located in ./Plugins. All classes which end in Plugin will be loaded.

        @return None
        """
        plugin_path = os.path.join(os.path.dirname(__file__), "Plugins")
        plugin_list = os.listdir(plugin_path)
        imported_plugins = None
        for plugin in plugin_list:
            if not plugin.endswith(".py"):
                continue
            plugin = str(plugin.rsplit(".")[0])
            if plugin == "__init__":
                continue

            imported_plugins = importlib.import_module("Bot.Plugins." + plugin)

        if imported_plugins is None:
            return

        available_classes = inspect.getmembers(imported_plugins, inspect.isclass)
        for classes in available_classes:
            if classes[0].endswith("Plugin"):
                self._pluginList.append(getattr(imported_plugins, classes[0])(self))

    def _init_networking(self, ip, port):
        """!
        @brief Initializes the networking module with the given ip and port.

        @param ip The IP to connect to
        @param port The port to connect to
        @return None
        """

        self._conn = Network.TCPConnection(ip, port)

    def connect(self):
        """!
        @brief Tries to open a connection to the ip and port supplied in the constructor.

        Requires a call to _init_networking before. Will connect to the ip and port which were supplied in that call.

        @return None
        """

        try:
            self._conn.connect()
            return True
        except ConnectionRefusedError:
            return False

    def disconnect(self):
        """!
        @brief Disconnects the TCP socket.

        @return None
        """

        self._conn.disconnect()

    def _message_available(self):
        """!
        @brief Returns whether the network connection holds a message which ends with \n\r.

        When this function encounters and error, it will call all LOST_CONNECTION callbacks.

        @return Boolean
        """

        try:
            return self._conn.message_available()
        except socket.error:
            self._call_callbacks(None, eventTypes.LOST_CONNECTION)

    def _get_next_message(self):
        """!
        @brief Returns the next message without a trailing \n\r

        @return String
        """

        try:
            return self._conn.get_next_message()
        except socket.error:
            self._call_callbacks(None, eventTypes.LOST_CONNECTION)

    def process(self):
        """!
        @brief Processes every message.

        Needs to be called every tick. Processes every available message as well as
        checks for timers which need to be called. When the bot lost connection, this function
        will also try to reestablish a connection.

        @return None
        """

        while self._conn.is_connected() and self._message_available():
            self._handle_message()
        self._timer.check_timers()
        if not self._conn.is_connected():
            if self.connect():
                self.login_use()

    def _handle_message(self):
        message = self._get_next_message()
        self._translate_message(message)

    def _translate_message(self, message):
        """!
        @brief Handles a single message sent by the teamspeak server query interface.

        @param message The message to be handled
        @return None
        """

        # print(message)
        if message == "TS3" or message == "Welcome to the TeamSpeak 3 ServerQuery interface, " \
                                          "type \"help\" for a list of commands and \"help <command>\" for " \
                                          "information on a specific command.":
            return

        args = normalize_message(message)
        if starts_with_c_i(message, "notify"):
            if message == self._lastLine:
                self._lastLine = message
                return
            self._lastLine = message
            event = Event(args)
            if starts_with_c_i(message, "notifycliententerview"):
                self._call_callbacks(event, eventTypes.CLIENT_JOINED)
            if starts_with_c_i(message, "notifyclientleftview"):
                self._call_callbacks(event, eventTypes.CLIENT_LEFT)
            if starts_with_c_i(message, "notifyclientmoved"):
                self._call_callbacks(event, eventTypes.CLIENT_MOVED)
            if starts_with_c_i(message, "notifytextmessage"):
                self._call_callbacks(event, eventTypes.PRIVATE_TEXT)
            return

        if starts_with_c_i(message, "error"):
            query = self._queryTracker.complete_last_query()
            error_id = args[0]["id"]
            if int(error_id) != 0:
                event = Event(args)
                event.data = {
                    "query": query.text,
                    "error_id": error_id,
                    "error_message": message
                }
            if query.errCallback:
                event = Event(args)
                event.data = query.data
                query.errCallback(event)
            return

        # Must be a query response
        query = self._queryTracker.get_last_uncompleted_query()
        event = Event(args)
        event.data = query.data
        if query.callback:
            query.callback(event)

    def _call_method_on_all_plugins(self, method_name, *args):
        """!
        @brief Calls a method on all plugins

        Iterates through all plugins and calls the given method.
        Can receive multiple arguments after the method name which are passed onto the called function

        @param method_name The method which to call
        @param args variable length of arguments which are passed into method_name
        @return None
        """

        for plugin in self._pluginList:
            getattr(plugin, method_name)(*args)

    def _call_callbacks(self, event, event_type):
        """!
        @brief Calls all callbacks appropriate for the given event_type

        @param event The event object which will be passed to the called functions
        @param event_type The event type for which the callbacks should be called
        @return None
        """

        if event is not None:
            event.Bot = self

        if event_type == eventTypes.CLIENT_JOINED:
            if int(event.args[0]["client_type"]) != 0:
                return
            self._on_client_joined(event)
            # This will be called inside the event handler,
            # as we need to update the client first to gain all necessary informations
            # self._callMethodOnAllPlugins("on_client_joined", event)

        if event_type == eventTypes.CLIENT_LEFT:
            if not self._dataManager.has_clid(event.args[0]["clid"]):
                return
            self._call_method_on_all_plugins("on_client_left", event)
            self._on_client_left(event)

        if event_type == eventTypes.CLIENT_MOVED:
            if not self._dataManager.has_clid(event.args[0]["clid"]):
                return
            event = self._on_client_moved(event)
            self._call_method_on_all_plugins("on_client_moved", event)

        if event_type == eventTypes.PRIVATE_TEXT:
            if not self._dataManager.has_clid(event.args[0]["invokerid"]):
                return
            event = self._on_private_text(event)
            if event:
                self._call_method_on_all_plugins("on_private_text", event)

        if event_type == eventTypes.LOST_CONNECTION:
            if self._conn.is_connected():
                self._call_method_on_all_plugins("on_connection_lost")
                self._on_connection_lost()

    def _on_client_joined(self, event):
        """!
        @brief Will be called everytime a client joins.

        The returned event will then be passed onto the plugin, as we inject values here.
        As we need to retrieve more data about the client from the server, this function will
        not call the plugin callbacks. But instead run a clientinfo on the connected client
        and pass control over to the callback _on_client_joined_updated_clientinfo.

        @param event The event object, which will later be passed to the plugins
        @return The event object, which will later be passed to the plugins
        """

        clid = event.args[0]["clid"]

        # Special treatment of "cid" and "ctid"
        # When a client connects ( enterview ) it will only have
        # its target channel id set, but it will not be set as its current channel
        # we're going to force that here
        event.args[0]["cid"] = event.args[0]["ctid"]

        self.send_command("clientinfo clid=%s" % str(clid), self._on_client_joined_updated_clientinfo,
                          {"join_data": event.args[0], "event": event})
        return event

    def _on_client_joined_updated_clientinfo(self, event):
        """!
        Called as a callback after a client joined. Adds additional data to the client connected event so that
        callbacks will receive a complete data set of that client. Will call servergroupsbyclientid on the
        connected client and pass control over to the callback on_client_joined_updated_servergroups.

        @param event The event object containing data related to the sent query
        @return None
        """

        complete_client_data = event.args[0].copy()
        complete_client_data.update(event.data["join_data"])
        self.send_command("servergroupsbyclientid cldbid=%s" % str(complete_client_data["client_database_id"]),
                          self._on_client_joined_updated_servergroups,
                          {"complete_client_data": complete_client_data, "event": event.data["event"]})

    def _on_client_joined_updated_servergroups(self, event):
        """!
        Adds the client groups to the event object and will finally call the plugin callbacks
        as well as add the client to the data manager.

        @param event The event object containing data related to the sent query
        @return None
        """
        self._dataManager.add_client(event.data["complete_client_data"]["clid"], event.data["complete_client_data"])
        self._dataManager.add_client_servergroups(event.data["complete_client_data"]["clid"], event.args, True)
        self._call_method_on_all_plugins("on_client_joined", event.data["event"])

    def _on_client_left(self, event):
        """!
        Called when a client leaves. Removes the client from the data manager and calls all plugin callbacks

        @param event The event object containing data related to the sent query
        @return None
        """

        clid = event.args[0]["clid"]
        self._dataManager.remove_client(clid)

    def _on_client_moved(self, event):
        """!
        Called when a client got moved. Updates the current channel of the client in the datamanger.

        @param event The event object containing data related to the sent query
        @return modified event object
        """

        clid = event.args[0]["clid"]
        ctid = event.args[0]["ctid"]
        old_channel = self._dataManager.get_client_value(clid, "cid", True)
        self._dataManager.set_client_value(clid, "cid", ctid, True)
        event.args[0]["cid"] = old_channel
        return event

    def _on_private_text(self, event):
        """!
        Called when the bot receives a private message. Will check whether the received
        message is a command. When it is, it will check whether the senders accesslevel
        is high enough for the command and call the plugin callbacks.

        @param event The event object containing data related to the sent query
        @return event object
        """

        if int(event.args[0]["targetmode"]) != 1:
            return False

        msg = event.args[0]["msg"]
        invokerid = event.args[0]["invokerid"]
        invokername = event.args[0]["invokername"]
        invokeruid = event.args[0]["invokeruid"]

        if not msg.startswith("."):
            return event

        msg_splitted = msg.split(" ")

        if not msg_splitted[0][1:] in self._chatCommands:
            return event

        chat_command = self._chatCommands[msg_splitted[0][1:]]

        invoker_access_level = self._dataManager.get_access_level_by_clid(invokerid)
        if invoker_access_level is None or chat_command.accessLevel > self._dataManager.get_access_level_by_clid(
                invokerid):
            self.send_command("sendtextmessage targetmode=1 target=%s msg=%s" %
                              (invokerid, escape("Your accesslevel is not high enough for this command.")))
            return event

        chat_command.callback(invokerid, invokername, invokeruid, msg_splitted[1:])
        return event

    def _on_connection_lost(self):
        """!
        Called when the bot loses connection the the teamspeak. Disconnects the socket, clears all remaining messages
        and clears all remaining queries and data.

        @return None
        """

        self.disconnect()
        self._conn.clear_message_buffer()
        self._dataManager.clear_all_data()
        self._queryTracker.reset()

    def _update_all_clients(self):
        """!
        Iterates through all online clients and calls _update_client on them

        @return None
        """

        online_clients = self._dataManager.get_clients()
        for clid in online_clients:
            self._update_client(clid)

    def _update_client(self, clid):
        """!
        Updates a single client. Calls _update_client_callback as a callback.

        @param clid The clientid of the client to update
        @return None
        """

        self.send_command("clientinfo clid=%s" % str(clid), self._update_client_callback, {"clid": int(clid)})

    def _update_client_callback(self, event):
        """!
        Called when a client got updated via _update_client. Updates all information
        in the datamanger and passes _on_client_value_changed as a possible callback for
        value changes.

        @param event The event object containing data related to the sent query
        @return None
        """

        self._dataManager.update_client(event.data["clid"], event.args[0], self._on_client_value_changed)

    def _on_client_value_changed(self, clid, key, old_value, value):
        """!
        Called when a client value changes. Will dispatch this change to all registered callbacks.

        @param clid The client id of the client whose value changed
        @param key The key of the changed value
        @param old_value The old value
        @param value The new value
        @return None
        """

        if key not in self._callbacksValueChanged:
            return
        for callback in self._callbacksValueChanged[key]:
            callback(clid, key, old_value, value)

    def _update_all_client_servergroups(self):
        """!
        Updates the servergroups of all clients. Needed to keep track of the access level.

        @return None
        """

        online_clients = self._dataManager.get_clients()
        for clid in online_clients:
            self._update_client_servergroups(clid)

    def _update_client_servergroups(self, clid):
        """!
        Updates the servergroups of a single client. Has _update_client_servergroups_callback as its callback.

        @param clid The client whose servergroups to update.
        @return None
        """

        cldbid = self._dataManager.get_client_cldbid_by_clid(clid)
        if cldbid is None:
            return
        self.send_command("servergroupsbyclientid cldbid=%s" % str(cldbid), self._update_client_servergroups_callback,
                          data=clid)

    def _update_client_servergroups_callback(self, event):
        """!
        Updates the client servergroups in the datamanager.

        @param event The event object containing data related to the sent query
        @return None
        """

        self._dataManager.add_client_servergroups(event.data, event.args, True)

    def send_command(self, message, callback=None, data=None, err_callback=None):
        """!
        @brief Sends a raw message to the teamspeak servers.

        Will send a raw command to the teamspeak server. You need to take care
        about escaping the sent message yourself. Refer to the teamspeak3 server
        query doc for more information.

        @param message The message to send
        @param callback The callback which will be called when the answer for the query arrives
        @param data Additional data which will be passed to the callback as event.data
        @param err_callback A callback which will be called when the query failed
        @return Boolean. True if the message was sent, false otherwise.
        """

        query = Bot.QueryManager.Query(callback, data, message, err_callback)
        self._queryTracker.add_query(query)
        try:
            self._conn.send_message(message + "\n\r")
            return True
        except socket.error:
            self._call_callbacks(None, eventTypes.LOST_CONNECTION)
            return False

    def _intialize_data(self):
        """!
        @brief Initializes the clientlist.

        @return None
        """

        self.send_command("clientlist", self._on_initial_clientlist)

    def _on_initial_clientlist(self, event):
        """!
        Called when the initial clientlist arrives. Clears all current clients and adds
        the received client. Will also request a channellist and provide _on_initial_channellist as a callback.

        @param event The event object containing data related to the sent query
        @return None
        """

        client_list = event.args
        client_list_without_server_queries = [client for client in client_list if client["client_type"] == '0']
        self._dataManager.add_clients(client_list_without_server_queries, clear=True)
        self.send_command("channellist", self._on_initial_channellist, data=client_list_without_server_queries)

    def _on_initial_channellist(self, event):
        """!
        Called when the initial channellist arrives. Clears all current channels and adds
        the received channels. Will also call the on_initial_data callback in all plugins

        @param event The event object containing data related to the sent query
        @return None
        """

        self._dataManager.add_channels(event.args)
        self._call_method_on_all_plugins("on_initial_data", event.data, event.args)

    # functions mainly intended for plugins
    def add_chat_command(self, command, description, access_level, callback, is_channel_command=False):
        """!
        @brief Adds a chat command.

        Adds a chat command to the bot. When is_channel_command is false, a user needs to private message the bot in order
        to trigger the command. Otherwise, the user needs to post that command in a channel. The command
        needs to be prefixed with the needed prefix provided in the config file.

        @param command The command the user needs to type ( without prefix )
        @param description A description of that command. Usefull in for help commands and similiar
        @param access_level The minimum accesslevel required for the command.
        @param callback A callback to call when a user triggers a command
        @param is_channel_command Whether the command should trigger in channels or in private messages
        @return None
        """

        if command in self._chatCommands:
            return False
        self._chatCommands[command] = ChatCommand(command, description, access_level, callback, is_channel_command)

    def get_client_value(self, clid, key):
        """!
        @brief Retrieves a client value.

        First, the teamspeak data namespace will be searched. If nothing is found,
        the custom data namespace will be searched. This means that custom keys cannot have the same name
        as a already existing teamspeak key otherwise it will be shadowed by the teamspeak key.

        Returns None when a key is not found in both namespaces.

        @param clid The client id whose value you want to retrieve
        @param key The key whose value you want to retrieve
        @return The value
        """

        value = self._dataManager.get_client_value(clid, key)
        return value

    def set_client_value(self, clid, key, value, persistent=False):
        """!
        @brief Sets a client value.

        If persistent is true, the value will be saved in the database.

        @param clid The client id to save the value for
        @param key The key for you value
        @param value Your value
        @param persistent Whether the value should be persistent. If true, it will be saved to the DB
            and will be retrieved the next time the client connects
        @return Boolean
        """

        if persistent:
            return self._dataManager.set_persistent_client_value(clid, key, value)
        else:
            return self._dataManager.set_client_value(clid, key, value, False, self._on_client_value_changed)

    def register_value_changed_callback(self, key, callback):
        """!
        @brief Registers a callback which will be called everytime the value with the given key changes

        @param key The key you want to watch
        @param callback The callback to call when the given key changes
        @return None
        """

        if key not in self._callbacksValueChanged:
            self._callbacksValueChanged[key] = []
        self._callbacksValueChanged[key].append(callback)

    # simple server query wrappers starting from here
    def send_server_notify_register(self, event, id=None):
        """!
        @brief Wraps servernotifyregister. See teamspeak query doc for more.

        @param event server|channel|textserver|textchannel|textprivate
        @param id channelID
        @return None
        """

        if id is not None:
            self.send_command("servernotifyregister event=" + event + " id=" + str(id))
        else:
            self.send_command("servernotifyregister event=" + event)

    # more complex server query wrappers encapsulating multiple commands into one function
    def login_use(self):
        """!
        @brief Logins with the provided credentials and choses a server.

        Calls login with the provided server query credentials during bot construction.
        After, it will call use with the provided virtual server id, register for all
        events and initialize the bot data.

        @return None
        """

        self.send_command("login {0} {1}".format(escape(self._user), escape(self._password)))
        self.send_command("use {0}".format(int(self._virtualServerId)))
        self.register_for_all_events()
        self._intialize_data()

    def register_for_all_events(self):
        """!
        @brief Registers for the following events: server, textprivate, channel, textchannel

        @return None
        """

        self.send_server_notify_register("server", 0)
        self.send_server_notify_register("textprivate", 0)
        self.send_server_notify_register("channel", 0)
        self.send_server_notify_register("textchannel")
