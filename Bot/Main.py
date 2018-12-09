# coding=utf-8
import inspect
from enum import Enum
import socket

import queue
import UnixServer
import Network
import Bot.MysqlManager
import Bot.QueryManager
import Bot.DataManager
import importlib
import os
import signal

from Bot.Utility import starts_with_c_i, normalize_message, Event, escape, Timer, ChatCommand

from Globals import config


class EventTypes(Enum):
    CLIENT_JOINED = 0
    CLIENT_LEFT = 1
    CLIENT_MOVED = 2
    CLIENT_SAY = 3
    TEXT = 4
    LOST_CONNECTION = 5


class CommandResults(Enum):
    # Used to indicate that the user is missing arguments. The bot will resend the command structure to the user
    INVALID_USE = 1


class TeamspeakBot:
    def __init__(self, ip, port=10011, user=None, password=None, virtual_server_id=None, minimal=False):
        """!
        @brief Constructs a TeamspeakBot instance

        @param ip Ip of the server you want to connect to
        @param port Port of the server yoú want to connect to
        @param user Serverquery username
        @param password Serverquery password
        @param virtual_server_id The virtual id of the serverr you want the bot to manage
        @param minimal Initializes a minimal bot version.
            The following will not be initialized: mysql, timer, plugins, ts3speech
        """

        self._conn = None
        self._my_clid = None

        self._init_networking(ip, port)
        self._ip = ip
        self._port = port

        self._user = user
        self._password = password
        self._virtualServerId = virtual_server_id

        self._queryTracker = Bot.QueryManager.QueryTracker()

        self._slaves = {}  # cid: slave_instance
        self._plugin_list = []
        self._command_prefix = config.get_value("command_prefix")

        self._lastLine = ""

        self._timer = Timer()
        self._timer.start_timer(self._send_heartbeat, 60000, False)
        self._timer.start_timer(lambda: self._queryTracker.clean_up(), 60000, False)

        self.minimal = minimal
        if minimal:
            self._dataManager = Bot.DataManager.DataManager(None)
            self._dataManager.set_default_access_level(config.get_value("accesslevel.default"))
            self._dataManager.set_access_levels(config.get_value("accesslevel.groups"))
            return

        self._mysqlManager = Bot.MysqlManager.MysqlManager()
        self._mysqlManager.connect_to_db(config.get_value("mysql.host"),
                                         config.get_value("mysql.port"),
                                         config.get_value("mysql.user"),
                                         config.get_value("mysql.password"),
                                         config.get_value("mysql.db"))

        self._dataManager = Bot.DataManager.DataManager(self._mysqlManager)
        self._dataManager.set_default_access_level(config.get_value("accesslevel.default"))
        self._dataManager.set_access_levels(config.get_value("accesslevel.groups"))

        ts3speech_socket = config.get_value("ts3speech_socket")
        self.ts3speech_socket = False
        if ts3speech_socket != "":
            self.ts3speech_queue = queue.Queue()
            self.ts3speech_server = UnixServer.UnixServer(self.ts3speech_queue, ts3speech_socket)
            self.ts3speech_server.start()
            self.ts3speech_socket = True

        self._timer.start_timer(self._update_all_clients, 250, False)
        self._timer.start_timer(self._update_all_client_servergroups, 250, False)
        self._timer.start_timer(self._update_all_client_db_accesslevel, 60000, False)

        if config.get_value("channel_text"):
            self._timer.start_timer(self._update_slaves, 250, False)
        self.bot_name = config.get_value("bot_name") or "Bot"
        self._callbacksValueChanged = {}
        self._chatCommands = {}

        self._setup_plugins()

        signal.signal(signal.SIGTERM, self.shutdown_signal)
        signal.signal(signal.SIGINT, self.shutdown_signal)

    def shutdown_signal(self, signum, frame):
        self.ts3speech_server.shutdown_flag.set()
        self.disconnect()
        self._conn.clear_message_buffer()
        self._dataManager.clear_all_data()
        self._queryTracker.reset()
        self._remove_all_slaves()
        exit(signum)

    def _setup_plugins(self):
        """!
        @brief initializes all plugins which are located in ./Plugins. All classes which end in Plugin will be loaded.

        @return None
        """

        if config.get_value("load_all_plugins"):
            plugin_path = os.path.join(os.path.dirname(__file__), "Plugins")
            plugin_list = os.listdir(plugin_path)
        else:
            plugin_list = config.get_value("plugin_list") or []
            plugin_list = ["{0}.py".format(plugin) for plugin in plugin_list]

        for plugin in plugin_list:
            if not plugin.endswith(".py"):
                continue
            plugin = str(plugin.rsplit(".")[0])
            if plugin.startswith("__"):
                continue

            imported_plugins = importlib.import_module("Bot.Plugins." + plugin)

            if imported_plugins is None:
                continue

            available_classes = inspect.getmembers(imported_plugins, inspect.isclass)
            for classes in available_classes:
                if classes[0].endswith("Plugin"):
                    self._plugin_list.append(getattr(imported_plugins, classes[0])(self))

        self._plugin_list = sorted(self._plugin_list, key=lambda plugin: plugin.order)

        pass

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
            self._call_callbacks(None, EventTypes.LOST_CONNECTION)

    def _get_next_message(self):
        """!
        @brief Returns the next message without a trailing \n\r

        @return String
        """

        try:
            return self._conn.get_next_message()
        except socket.error:
            self._call_callbacks(None, EventTypes.LOST_CONNECTION)

    def process(self):
        """!
        @brief Processes every message.

        Needs to be called every tick. Processes every available message as well as
        checks for timers which need to be called. When the bot lost connection, this function
        will also try to reestablish a connection.

        @return None
        """

        while not self.minimal and self.ts3speech_socket and not self.ts3speech_queue.empty():
            item = self.ts3speech_queue.get_nowait()
            event = Event([{"clid": item[0], "text": item[1].decode("utf-8")}])
            self._call_callbacks(event, EventTypes.CLIENT_SAY)

        while self._conn.is_connected() and self._message_available():
            self._handle_message()

        for idx in self._slaves:
            slave = self._slaves[idx]
            slave.process()

        if hasattr(self, "_timer"):
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
                self._call_callbacks(event, EventTypes.CLIENT_JOINED)
            if starts_with_c_i(message, "notifyclientleftview"):
                self._call_callbacks(event, EventTypes.CLIENT_LEFT)
            if starts_with_c_i(message, "notifyclientmoved"):
                self._call_callbacks(event, EventTypes.CLIENT_MOVED)
            if starts_with_c_i(message, "notifytextmessage"):
                self._call_callbacks(event, EventTypes.TEXT)
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

        for plugin in self._plugin_list:
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

        if event_type == EventTypes.CLIENT_JOINED:
            if int(event.args[0]["client_type"]) != 0:
                self._dataManager.add_client(event.args[0]["clid"], event.args[0])
                return
            self._on_client_joined(event)
            # This will be called inside the event handler,
            # as we need to update the client first to gain all necessary informations
            # self._callMethodOnAllPlugins("on_client_joined", event)

        if event_type == EventTypes.CLIENT_LEFT:
            if self._dataManager.get_client_value(event.args[0]["clid"], "client_type", None, True) is not None and \
                            int(self._dataManager.get_client_value(event.args[0]["clid"], "client_type", None,
                                                                   True)) != 0:
                self._on_client_left(event)
                return
            self._call_method_on_all_plugins("on_client_left", event)
            self._on_client_left(event)

        if event_type == EventTypes.CLIENT_MOVED:
            if self._dataManager.get_client_value(event.args[0]["clid"], "client_type", None, True) is not None and \
                            int(self._dataManager.get_client_value(event.args[0]["clid"], "client_type", None,
                                                                   True)) != 0:
                return
            event = self._on_client_moved(event)
            self._call_method_on_all_plugins("on_client_moved", event)

        if event_type == EventTypes.TEXT:
            if self._dataManager.get_client_value(event.args[0]["invokerid"], "client_type", None, True) is not None \
                    and int(
                        self._dataManager.get_client_value(event.args[0]["invokerid"], "client_type", None, True)) != 0:
                return
            event = self._on_text(event)
            if event:
                self._call_method_on_all_plugins("on_private_text", event)

        if event_type == EventTypes.CLIENT_SAY:
            if self._dataManager.get_client_value(event.args[0]["clid"], "client_type", None, True) is not None \
                    and int(
                        self._dataManager.get_client_value(event.args[0]["clid"], "client_type", None, True)) != 0:
                return
            self._call_method_on_all_plugins("on_client_say", event)

        if event_type == EventTypes.LOST_CONNECTION:
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

        clid = event.data["complete_client_data"]["clid"]
        self._dataManager.add_client(clid, event.data["complete_client_data"])
        self._dataManager.add_client_servergroups(clid, event.args, True)
        self._update_client_db_accesslevel(clid)
        self._update_client_remote_ip(clid)
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
        old_channel = self._dataManager.get_client_value(clid, "cid", None, True)
        self._dataManager.set_client_value(clid, "cid", ctid, True)
        event.args[0]["cid"] = old_channel
        return event

    def _on_text(self, event):
        """!
        Called when the bot receives a private/channel message. Will check whether the received
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

        if not msg.startswith(self._command_prefix):
            return event

        msg_splitted = msg.split(" ")

        if not msg_splitted[0][1:].lower() in self._chatCommands:
            return event

        chat_command = self._chatCommands[msg_splitted[0][1:].lower()]

        if chat_command.is_channel_command:
            return event

        invoker_access_level = self._dataManager.get_access_level_by_clid(invokerid)
        if invoker_access_level is None or chat_command.accesslevel > invoker_access_level:
            self.send_command("sendtextmessage targetmode=1 target=%s msg=%s" %
                              (invokerid, escape("Your accesslevel is not high enough for this command.")))
            return event

        result = chat_command.callback(int(invokerid), invokername, invokeruid, msg_splitted[1:])
        self._process_command_result(invokerid, chat_command, result)

        return event

    def _process_command_result(self, invokerid, chat_command, result):
        """!
        @brief Processes the result of a called callback of a command.

        @param result The result of the called command callback
        @return None
        """
        if result == CommandResults.INVALID_USE:
            self.send_text_to_client(invokerid,
                                     "Invalid command! Please use {0}{1} {2}".format(self._command_prefix,
                                                                                     chat_command.original_command,
                                                                                     " ".join(chat_command.args)))

    def _on_channel_text(self, event):
        if int(event.args[0]["targetmode"]) != 2:
            return False

        msg = event.args[0]["msg"]
        invokerid = event.args[0]["invokerid"]
        invokername = event.args[0]["invokername"]
        invokeruid = event.args[0]["invokeruid"]

        if not msg.startswith("."):
            return self._call_method_on_all_plugins("on_channel_text", event)

        msg_splitted = msg.split(" ")

        if not msg_splitted[0][1:] in self._chatCommands:
            return self._call_method_on_all_plugins("on_channel_text", event)

        chat_command = self._chatCommands[msg_splitted[0][1:]]

        if not chat_command.is_channel_command:
            return self._call_method_on_all_plugins("on_channel_text", event)

        invoker_access_level = self._dataManager.get_access_level_by_clid(invokerid)
        if invoker_access_level is None or chat_command.accesslevel > invoker_access_level:
            return self._call_method_on_all_plugins("on_channel_text", event)

        chat_command.callback(int(invokerid), invokername, invokeruid, msg_splitted[1:])
        return self._call_method_on_all_plugins("on_channel_text", event)

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
        self._remove_all_slaves()

    def _set_bot_name(self):
        """!
        @brief This will set the bots name to the one specified in the config file.

        @return None
        """
        self.send_command("clientupdate client_nickname=" + escape(self.bot_name))

    def _update_all_clients(self):
        """!
        @brief Iterates through all online clients and calls _update_client on them

        @return None
        """

        online_clients = self._dataManager.get_clients()
        for clid in online_clients:
            self._update_client(clid)

    def _update_client(self, clid):
        """!
        @brief Updates a single client. Calls _update_client_callback as a callback.

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
        @brief Called when a client value changes. Will dispatch this change to all registered callbacks.

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

    def _update_all_client_db_accesslevel(self):
        """!
        @brief Updates all accesslevels in the db

        @return None
        """
        online_clients = self._dataManager.get_clients()
        for clid in online_clients:
            self._update_client_db_accesslevel(clid)

    def _update_client_db_accesslevel(self, clid):
        """!
        @brief Updates the accesslevel for the given client in the database

        @param clid Client for which to update the accesslevel
        @return None
        """
        self._dataManager.update_client_accesslevel(clid)

    def _update_client_remote_ip(self, clid):
        """!
        @brief Updates the remote_ip of the given client in the database

        @param clid Client for which to update the accesslevel
        @return None
        """
        self.send_command("clientinfo clid=%s" % str(clid),
                          lambda event: self._dataManager.update_client_ip(
                              event.data["clid"], event.args[0]["connection_client_ip"]
                          ),
                          {"clid": int(clid)})

    def _update_all_client_servergroups(self):
        """!
        @brief Updates the servergroups of all clients. Needed to keep track of the access level.

        @return None
        """

        online_clients = self._dataManager.get_clients()
        for clid in online_clients:
            self._update_client_servergroups(clid)

    def _update_client_servergroups(self, clid):
        """!
        @brief Updates the servergroups of a single client. Has _update_client_servergroups_callback as its callback.

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
        @brief Updates the client servergroups in the datamanager.

        @param event The event object containing data related to the sent query
        @return None
        """

        self._dataManager.add_client_servergroups(event.data, event.args, True)

    def _send_heartbeat(self):
        """
        @brief Sends an heartbeat to the server to avoid getting the connection dropped due to inactivity

        @return None
        """
        self.send_command("whoami")

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
        if not self._conn.is_connected():
            return False

        query = Bot.QueryManager.Query(callback, data, message, err_callback)
        self._queryTracker.add_query(query)
        try:
            self._conn.send_message(message + "\n\r")
            return True
        except socket.error:
            self._call_callbacks(None, EventTypes.LOST_CONNECTION)
            return False

    def _intialize_data(self):
        """!
        @brief Initializes the clientlist.

        @return None
        """

        self.send_command("whoami", self._on_initial_whoami)

    def _on_initial_whoami(self, event):
        """!
        @brief Initializes the bots own client id and calls further init functions

        @param event The event object containing data related to the sent query
        @return None
        """
        self._my_clid = event.args[0]["client_id"]
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
        self._dataManager.add_clients(client_list, clear=True)

        for client_id in self.get_clients():
            self._update_client_remote_ip(client_id)

        self.send_command("channellist", self._on_initial_channellist, data=client_list_without_server_queries)

    def _on_initial_channellist(self, event):
        """!
        Called when the initial channellist arrives. Clears all current channels and adds
        the received channels. Will also call the on_initial_data callback in all plugins

        @param event The event object containing data related to the sent query
        @return None
        """

        self._set_bot_name()
        self._dataManager.add_channels(event.args)
        self._update_all_client_servergroups()
        self._call_method_on_all_plugins("on_initial_data", event.data, event.args)

    def _on_initial_server_servergroups(self):
        pass

    # everything for slaves ( receiving channel messages ) here
    def _update_slaves(self):
        """!
        Will initiate new slaves and delete the slaves sitting in empty channels. All those slaves
        are used to relay channel text messages to the main bot in order to fire events.

        @return None
        """
        channels_with_clients = set(
            [int(self._dataManager.get_client_value(clid, "cid", None, True)) for clid in
             self._dataManager.get_clients()]
        )
        for cid in channels_with_clients:
            if cid not in self._slaves:
                self._add_slave(cid)
        for cid in dict(self._slaves):
            if cid not in channels_with_clients:
                self._remove_slave(cid)

    def _add_slave(self, cid):
        """!
        Adds a slave to the given channel. If a slave already exists this will do nothing.

        @param cid The channel id to which the slave will join.
        @return None
        """
        if cid in self._slaves:
            return
        self._slaves[cid] = BotChannelSlave(self._ip, self._port, self._user, self._password,
                                            self._virtualServerId, cid, self._on_channel_text)

    def _remove_slave(self, cid):
        """!
        Removes the slave from the given channel. If that channel has no slave this will do nothing.

        @param cid The channel id from which the slave should be removed.
        @return None
        """
        if cid not in self._slaves:
            return

        self._slaves[cid].kill()
        del self._slaves[cid]

    def _remove_all_slaves(self):
        """
        @brief Disconnects and removes all slaves

        @return None
        """
        for cid in dict(self._slaves):
            self._remove_slave(cid)

    # functions mainly intended for plugins
    def add_chat_command(self, command, description, access_level, callback, args=None, is_channel_command=False):
        """!
        @brief Adds a chat command.

        Adds a chat command to the bot. When is_channel_command is false, a user needs to private
        message the bot in order to trigger the command. Otherwise, the user needs to post that
        command in a channel. The command needs to be prefixed with the needed prefix provided in the config file.

        Your callback can return predefined values to indicate its result or state, e.g when the user
        did not provide all needed arguments you can return self.bot_instance.CommandResults.INVALID_USE to
        trigger a message to the sender indicating the right command structure. All possible values are defined in
        CommandResults

        @param command The command the user needs to type ( without prefix )
        @param description A description of that command. Usefull in for help commands and similiar
        @param access_level The minimum accesslevel required for the command.
        @param callback A callback to call when a user triggers a command
        @param args An array of strings of args you expect. You have to parse them yourself, this is only to help the
                    user about expected arguments.
        @param is_channel_command Whether the command should trigger in channels or in private messages
        @return None
        """

        if args is None:
            args = []
        if command in self._chatCommands:
            return False

        self._chatCommands[command.lower()] = ChatCommand(command, description, int(access_level), callback,
                                                          args,
                                                          is_channel_command)

    def get_all_commands(self):
        """!
        Returns an dictionary with an instance of all commands. An instance holds the following members:

        command - The command, converted to lowercase
        original_command - The original command, as it was provided by the plugin author ( no case conversion )
        description - A description of that command, as provided by the plugin author
        accesslevel - The required accesslevel for that command
        is_channel_command - Whether is is a channel command or noth
        callback - The callback to call when the command was executed by a user
        args - The args of that command, an array of ( one-word ) strings used to describe possible args of that command

        @return An dictionary of commands, where the command is the key and the instance is the value
        """
        return self._chatCommands

    def set_value(self, key, value):
        """!
        @brief Sets a persistent value which is saved in the database and can be retrieved later.

        @param key Identifier for you value
        @param value Value to set
        @return None
        """
        return self._dataManager.set_value(key, value)

    def get_value(self, key, default_value=None):
        """!
        @brief Retrieves a persistent value identified by key which was set earlier.

        @param key
        @param default_value The default value to return when the key was not found
        @return Value
        """
        return self._dataManager.get_value(key, default_value)

    @staticmethod
    def get_user_setting(key_path):
        """!
        @brief Returns the value of an user setting.

        This function returns the value of an user setting.
        These are values the user can define inside their config.json.
        The key can be a path to a value ( separated with . )
        which will correspond to a key nested inside the json document.

        E.g:

            key_path = MyPlugin.youtube.api_key

        would correspond to the following structure inside config.json:

        ```
                {
                    "chosen_config_namespace": {
                        "plugins": {
                            "MyPlugin": {
                                "youtube": {
                                    "api_key": "000000000000000"
                                }
                            }
                        }
                    }
                }
        ```

        The config namespace and the plugins key be prepended automatically.

        @param key_path The path to the value
        @return The value at the given path
        """
        return config.get_value("plugins." + key_path)

    def get_clients(self):
        """!
        @brief Returns an array of currently connected client ids. This excludes server query clients.

        @return Array of integers
        """
        return self._dataManager.get_clients()

    def get_clients_cldbid(self):
        """!
        @brief Returns an array of currently connected client database ids. This excludes server query clients.

        @return Array of integers
        """
        return self._dataManager.get_clients_cldbid()

    def get_client_value(self, clid, key, default_value=None):
        """!
        @brief Retrieves a client value.

        First, the teamspeak data namespace will be searched. If nothing is found,
        the custom data namespace will be searched. This means that custom keys cannot have the same name
        as a already existing teamspeak key otherwise it will be shadowed by the teamspeak key.

        Returns None when a key is not found in both namespaces.

        @param clid The client id whose value you want to retrieve
        @param key The key whose value you want to retrieve
        @param default_value The value to return when the clid does not exist or the key could not be found
        @return The value or the default_value of no entry was found
        """
        if clid is None:
            return default_value
        value = self._dataManager.get_client_value(clid, key, default_value)
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

    def start_timer(self, callback, interval, is_single_shot=False, *args):
        """!
        @brief A timer will be started and the callback will be called after interval seconds with the given args.

        A timer will be started an the callback will be called after interval seconds. When is_single_shot
        was set to true, the timer will be automatically removed after it was fired. All additional args are passed
        onto the given callback.

        @param callback The callback to call after the interval
        @param interval The time between successive calls
        @param is_single_shot Whether the timer will be deleted after it fired the first time
        @param args Additional args to pass onto the callback
        @return Integer A identifier for the timer used to delete it
        """
        return self._timer.start_timer(callback, interval, is_single_shot, *args)

    def stop_timer(self, timer_id):
        """!
        @brief Deletes the set timer with the given id. Returns true when a timer with that id was deleted.

        @param timer_id The id returned by start_timer for the started timer.
        @return True when the timer was found and deleted, false otherwise.
        """
        if timer_id is None:
            return False
        return self._timer.remove_timer(timer_id)

    def is_clid_online(self, clid):
        """!
        @brief Returns true when the given clid is currently online

        @param clid The client id to check
        @return True when the clid is online, false otherwise
        """
        return self.get_client_cldbid_by_clid(clid) is not None

    def is_cldbid_online(self, cldbid):
        """!
        @brief Returns true when the given cldbid is currently online

        @param cldbid The client database id to check
        @return True when the cldbid is online, false otherwise
        """
        return self.get_client_clid_by_cldbid(cldbid) is not None

    def get_client_cldbid_by_clid(self, clid):
        """!
        @brief Returns the client database id which belongs to the given client id.

        @param clid The client id
        @return The client database id or none
        """
        return self._dataManager.get_client_cldbid_by_clid(clid)

    def get_client_clid_by_cldbid(self, cldbid):
        """!
        @brief Returns the client id which belongs to the given client database id.

        @param cldbid The client database id
        @return The client id or none
        """
        return self._dataManager.get_client_clid_by_cldbid(cldbid)

    def get_client_accesslevel(self, clid):
        """!
        @brief Returns the client accesslevel for the given client id.

        @param clid Clientid to return the accesslevel for
        @return Accesslevel of default accesslevel
        """
        return self._dataManager.get_access_level_by_clid(clid)

    def get_mysql_instance(self):
        """!
        @brief Returns a handle to the mysql instance to perform raw queries.

        @return MysqlClass
        """
        return self._mysqlManager

    def execute_query(self, query, *args):
        """!
        @brief Executes a raw query on the mysql database.

        We are using pymysql with a dict cursor in the backend. Refer to the
        pymysql documentation for more information: http://pymysql.readthedocs.io/en/latest/modules/cursors.html
        This function wraps "execute" and the args will be passed on.

        @param query:
        @param args A
        @return The cursor object
        """
        return self._mysqlManager.execute_query(query, *args)

    # simple server query wrappers starting from here
    def send_server_notify_register(self, event, idd=None):
        """!
        @brief Wraps servernotifyregister. See teamspeak query doc for more.

        @param event server|channel|textserver|textchannel|textprivate
        @param idd channelID
        @return None
        """

        if idd is not None:
            self.send_command("servernotifyregister event=" + event + " id=" + str(idd))
        else:
            self.send_command("servernotifyregister event=" + event)

    def switch_to_channel(self, cid):
        """!
        @brief Switches the bot instance to the given channel id

        @param cid The channel id the bot should switch into
        @return None
        """
        self.send_command("clientmove clid=%s cid=%s" % (self._my_clid, cid))

    def switch_client_to_channel(self, clid, cid):
        """!
        @brief Switches a client to the given channel id

        @param clid The client id to switch
        @param cid The channel id the client should be switched to
        @return None
        """
        self.send_command("clientmove clid=%s cid=%s" % (clid, cid))

    def servergroupaddclient(self, sgid, cldbid, callback=None, data=None, err_callback=None):
        """!
        @brief Adds the given client ot the given servergroup

        @param sgid The id of the servergroup which the client will receive
        @param cldbid The database id of the client which will receive the servergroup
        @param callback Will be called when the query result are received
        @param data Additional data to pass to the callback
        @param err_callback Will be called when the query results in a error
        @return None
        """

        self.send_command("servergroupaddclient sgid={0} cldbid={1}".format(
            int(sgid), int(cldbid)
        ), callback, data, err_callback)

    def servergroupdelclient(self, sgid, cldbid, callback=None, data=None, err_callback=None):
        """!
        @brief Removes the given client from the given servergroup

        @param sgid The id of the servergroup from which the client will be removed
        @param cldbid The database id of the client which will be removed from the given servergroup
        @param callback Will be called when the query result are received
        @param data Additional data to pass to the callback
        @param err_callback Will be called when the query results in a error
        @return None
        """

        self.send_command("servergroupdelclient sgid={0} cldbid={1}".format(
            int(sgid), int(cldbid)
        ), callback, data, err_callback)

    def send_text_to_client(self, clid, message, callback=None, data=None, err_callback=None):
        """!
        @brief Sends a message to a client

        @param clid The client id which will receive the message
        @param message The message to send to the client
        @param callback Will be called when the query result are received
        @param data Additional data to pass to the callback
        @param err_callback Will be called when the query results in a error
        @return None
        """
        self.send_command("sendtextmessage targetmode=1 target={0} msg={1}".format(
            clid, escape(message)
        ), callback, data, err_callback)

    def send_text_to_channel(self, cid, message):
        """!
        @brief Sends a text message in a channel

        @param cid Channel id
        @param msg Message to send
        @return None
        """
        self.switch_to_channel(cid)
        self.send_command("sendtextmessage targetmode=2 target={0} msg={1}".format(
            cid, escape(message)
        ))

    # more complex server query wrappers encapsulating multiple commands into one function
    def login_use(self, register_for_events=True):
        """!
        @brief Logins with the provided credentials and choses a server.

        Calls login with the provided server query credentials during bot construction.
        After, it will call use with the provided virtual server id, register for all
        events and initialize the bot data.

        @param register_for_events Whether the bot instance should register for events server|textprivate|channelk
        @return None
        """

        self.send_command("login {0} {1}".format(escape(self._user), escape(self._password)))
        self.send_command("use {0}".format(int(self._virtualServerId)))
        if register_for_events:
            self.register_for_all_events()
        self._intialize_data()

    def register_for_all_events(self):
        """!
        @brief Registers for the following events: server, textprivate, channel

        @return None
        """

        self.send_server_notify_register("server", 0)
        self.send_server_notify_register("textprivate", 0)
        self.send_server_notify_register("channel", 0)
        #  self.send_server_notify_register("textchannel")


class BotChannelSlave(TeamspeakBot):
    def __init__(self, ip, port=10011, user=None, password=None,
                 virtual_server_id=None, cid=None, channel_text_callback=None):
        super().__init__(ip, port, user, password, virtual_server_id, minimal=True)

        success = self.connect()

        if not success:
            print("A slave had trouble to connect")
            exit()

        self.login_use(register_for_events=False)

        self._target_cid = cid

        self.send_server_notify_register("textchannel")
        self._channel_text_callback = channel_text_callback
        self._cid = cid

    def _on_initial_whoami(self, event):
        self._my_clid = event.args[0]["client_id"]
        self.switch_to_channel(self._target_cid)

    def _on_text(self, event):
        event.args[0]["cid"] = self._cid
        self._channel_text_callback(event)

    def kill(self):
        self.disconnect()
