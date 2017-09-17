from Bot.Plugins.Base import BasePlugin


class TestPlugin(BasePlugin):
    def __init__(self, bot_instance):
        super().__init__(bot_instance)
        # print("Test Plugin created")

    def on_initial_data(self, client_list, channel_list):
        # print("Look! The Bot just initialized! We got %d clients and %d channels"
        #      % (len(client_list), len(channel_list)))
        if len(client_list) <= 0:
            return
        # self._bot_instance.send_command("clientlist", callback=lambda e: print(e.args))
        self.bot_instance.send_command("sendtextmessage target=%s targetmode=1 msg=Hello" % client_list[0]["clid"])
        # self._bot_instance.add_chat_command("test1", "This is a test command", 0, self.on_test_command)
        # self._bot_instance.add_chat_command("test2", "This is a test command", 0, self.on_test_command, True)
        # self._bot_instance.add_chat_command("test2", "This is a test command", 5, self.on_test_command)
        # self._bot_instance.add_chat_command("test3", "This is a test command", 9, self.on_test_command)
        # self._bot_instance.add_chat_command("test4", "This is a test command", 10, self.on_test_command)
        # self._bot_instance.add_chat_command("test5", "This is a test command", 11, self.on_test_command)
        # print(self._bot_instance.get_client_value(client_list[0]["clid"], "test"))
        # print(self._bot_instance.set_client_value(client_list[0]["clid"], "test", 2, True))
        # print(self._bot_instance.get_client_value(client_list[0]["clid"], "test"))
        # print(self._bot_instance.get_value("test"))
        # print(self._bot_instance.set_value("test", 10))
        # print(self._bot_instance.get_value("test"))
        # mysql = self._bot_instance.get_mysql_instance()
        # ret = mysql.get_value("test")
        pass

    def on_test_command(self, *args):
        print(args)

    def on_client_joined(self, event):
        print("on_client_joined")
        print(event.args)

    def on_client_left(self, event):
        print("on_client_left")
        print(event.args)

    def on_client_moved(self, event):
        print("on_client_moved")
        print(event.args)

    def on_private_text(self, event):
        print("on_private_text")
        print(event.args)

    def on_channel_text(self, event):
        print("on_channel_text")
        print(event.args)

    def on_connection_lost(self):
        print("on_connection_lost")
