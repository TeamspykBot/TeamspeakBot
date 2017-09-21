class DataManager:
    def __init__(self, mysql_manager=None):
        self._clientList = {}
        self._channelList = {}
        self._accessLevels = {}
        self._defaultAccessLevel = 0
        self._mysqlManager = mysql_manager
        self._settings = {}

    def get_client_cldbid_by_clid(self, clid):
        clid = int(clid)
        if clid not in self._clientList:
            return None
        return int(self._clientList[clid]["teamspeak_data"]["client_database_id"])

    def get_client_clid_by_cldbid(self, cldbid):
        for clid in self._clientList:
            client = self._clientList[clid]
            if client["teamspeak_data"]["client_database_id"] == str(cldbid):
                return int(clid)
        return None

    def add_client(self, clid, client_data):
        if self._mysqlManager:
            self._mysqlManager.add_online_client(client_data["clid"], client_data["client_database_id"],
                                                 client_data["client_nickname"], "0.0.0.0", self._defaultAccessLevel)

        self._clientList[int(clid)] = {
            "teamspeak_data": client_data,
            "custom_data": self._mysqlManager.get_client_values(client_data["client_database_id"]) if self._mysqlManager
            else {},
            "servergroups": {}
        }

    def add_clients(self, clients, clear=False):
        if clear:
            self._clientList.clear()
            if self._mysqlManager:
                self._mysqlManager.clear_online_clients()
        for client in clients:
            self.add_client(client["clid"], client)

    def update_client(self, clid, client_data, data_changed_callback=None):
        if not self.has_clid(clid):
            return None

        for clientProperty in client_data:
            self.set_client_value(clid, clientProperty, client_data[clientProperty], True, data_changed_callback)

    def update_client_accesslevel(self, clid):
        if self._mysqlManager is None:
            return
        accesslevel = self.get_access_level_by_clid(clid)
        self._mysqlManager.set_client_accesslevel(clid, accesslevel)

    def has_clid(self, clid):
        if int(clid) in self._clientList:
            return True
        return False

    def remove_client(self, clid):
        if self._mysqlManager:
            self._mysqlManager.remove_online_client(clid)
        self._clientList.pop(int(clid), None)

    def get_clients(self):
        wsq = [client for client in self._clientList if
               self._clientList[client]["teamspeak_data"]["client_type"] == '0']
        return list(wsq)

    def get_clients_cldbid(self):
        wsq = [self._clientList[client]["teamspeak_data"]["client_database_id"] for client in self._clientList if
               self._clientList[client]["teamspeak_data"]["client_type"] == '0']
        return list(wsq)

    def set_client_value(self, clid, key, value, teamspeak_data=False, data_changed_callback=None):
        clid = int(clid)
        key = str(key)

        if clid not in self._clientList:
            return False

        old_value = self.get_client_value(clid, key, None, teamspeak_data)

        namespace = "teamspeak_data" if teamspeak_data else "custom_data"

        self._clientList[clid][namespace][key] = value

        if old_value is not None and data_changed_callback is not None and value != old_value:
            data_changed_callback(clid, key, old_value, value)
        return True

    def get_client_value(self, clid, key, default_value=None, teamspeak_data=None):
        clid = int(clid)
        key = str(key)

        if teamspeak_data is None:
            return self._get_client_value_for_namespace(clid, key, "teamspeak_data", default_value) or \
                   self._get_client_value_for_namespace(clid, key, "custom_data", default_value)

        if teamspeak_data is True:
            return self._get_client_value_for_namespace(clid, key, "teamspeak_data", default_value)

        if teamspeak_data is False:
            return self._get_client_value_for_namespace(clid, key, "custom_data", default_value)

    def set_persistent_client_value(self, clid, key, value):
        if self._mysqlManager is None:
            return
        clid = int(clid)
        cldbid = self.get_client_cldbid_by_clid(clid)
        if cldbid is None:
            return False
        key = str(key)

        self._mysqlManager.set_client_value(cldbid, key, value)
        self._clientList[clid]["custom_data"][key] = value
        return True

    def _get_client_value_for_namespace(self, clid, key, namespace, default_value=None):
        clid = int(clid)
        if clid not in self._clientList:
            return default_value
        if namespace not in self._clientList[clid]:
            return default_value
        if key not in self._clientList[clid][namespace]:
            return default_value
        return self._clientList[clid][namespace][key]

    def add_client_servergroup(self, clid, sgid, name):
        clid = int(clid)
        sgid = int(sgid)
        if not self.has_clid(clid):
            return False

        if name in self._clientList[clid]["servergroups"]:
            return True

        self._clientList[clid]["servergroups"][name] = sgid
        return True

    def add_client_servergroups(self, clid, servergroup_dictionary, clear=False):
        clid = int(clid)
        if not self.has_clid(clid):
            return
        if clear:
            self._clientList[clid]["servergroups"].clear()
        for servergroup in servergroup_dictionary:
            self.add_client_servergroup(clid, servergroup["sgid"], servergroup["name"])

    def remove_client_servergroup(self, clid, name):
        clid = int(clid)
        if not self.has_clid(clid):
            return False

        if name in self._clientList[clid]["servergroups"]:
            self._clientList[clid]["servergroups"].pop(name, None)
            return True
        return False

    def add_channel(self, cid, channel_data):
        self._channelList[cid] = {
            "teamspeak_data": channel_data,
            "custom_data": {}
        }

    def add_channels(self, channels, clear=False):
        if clear:
            self._channelList.clear()

        for channel in channels:
            self.add_channel(int(channel["cid"]), channel)

    def remove_channel(self, cid):
        self._channelList.pop(int(cid), None)

    def set_default_access_level(self, access_level):
        self._defaultAccessLevel = access_level

    def set_access_levels(self, access_level_map):
        self._accessLevels = access_level_map

    def get_access_level_by_clid(self, clid):
        clid = int(clid)
        if not self.has_clid(clid):
            return None
        highest_access_level = self._defaultAccessLevel
        for servergroup in self._clientList[clid]["servergroups"]:
            if servergroup in self._accessLevels and self._accessLevels[servergroup] > highest_access_level:
                highest_access_level = self._accessLevels[servergroup]
        return highest_access_level

    def clear_all_data(self):
        self._clientList.clear()
        self._channelList.clear()
        self._accessLevels.clear()

    def set_value(self, key, value):
        return self._mysqlManager.set_value(key, value)

    def get_value(self, key, default_value=None):
        return self._mysqlManager.get_value(key, default_value)
