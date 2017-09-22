# coding=utf-8

import time
from Globals import config
from Bot.Main import TeamspeakBot


def main():
    teamspeak_query_host = config.get_value("serverquery.host")
    teamspeak_query_user = config.get_value("serverquery.user")
    teamspeak_query_password = config.get_value("serverquery.password")
    teamspeak_query_virtual_server_id = config.get_value("serverquery.virtualserverid")

    bot = TeamspeakBot(teamspeak_query_host, user=teamspeak_query_user, password=teamspeak_query_password,
                       virtual_server_id=teamspeak_query_virtual_server_id)
    success = bot.connect()

    if not success:
        print("Error connecting to teamspeak server query interface.")
        exit()

    bot.login_use()

    while True:
        time.sleep(10 / 1000)
        bot.process()


if __name__ == "__main__":
    main()
