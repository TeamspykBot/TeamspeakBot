import ConfigManager

config = ConfigManager.ConfigManager("config.json")
environment = config.get_value("config_namespace")
