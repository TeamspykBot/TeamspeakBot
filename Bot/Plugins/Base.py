from Bot.Main import CommandResults, TeamspeakBot


class PluginBase:
    def __init__(self, bot_instance):
        self.bot_instance = bot_instance        # type: TeamspeakBot
        self.CommandResults = CommandResults
        self.order = 0

    def on_initial_data(self, client_list, channel_list):
        pass

    def on_client_joined(self, event):
        pass

    def on_client_left(self, event):
        pass

    def on_client_moved(self, event):
        pass

    def on_private_text(self, event):
        pass

    def on_channel_text(self, event):
        pass

    def on_client_say(self, event):
        pass

    def on_connection_lost(self):
        pass
