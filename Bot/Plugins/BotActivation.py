from Bot.Plugins.Base import PluginBase


class BotActivationPlugin(PluginBase):
    """
    This plugin will write the user when he renames himself to have 'bot' in his name.

    The plugin provides no commands.

    This plugin provides no configuration ( yet ).
    """

    def __init__(self, bot_instance):
        super().__init__(bot_instance)
        self.bot_instance.register_value_changed_callback("client_nickname", self.on_nick_changed)

    def on_nick_changed(self, clid, key, old_value, value):
        if "bot" in str(value).lower():
            self.bot_instance.send_text_to_client(clid, "Hello " + value + ".")
