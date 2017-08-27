import os
import json


class ConfigManager:
    def __init__(self, config_name):
        # Path Stuff
        self._configPath = os.path.join(os.path.dirname(__file__), config_name)
        # ----------

        if not os.path.exists(self._configPath):
            print("Config not found.. exiting.")
            exit()

        file_handle = open(self._configPath, 'r', encoding="utf-8")
        try:
            self._config = json.loads(file_handle.read())
        except ValueError as e:
            print(e)
            print("Config not valid.")
            exit()
        file_handle.close()

    def get_value(self, key):
        key_path = key.split(".")
        if len(key_path) == 1:
            return self._config[key]
        cfg = self._config
        for entry in key_path:
            cfg = cfg[entry]
        return cfg
