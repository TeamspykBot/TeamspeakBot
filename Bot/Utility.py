# coding=utf-8
import re
import time
import os


def log(message):
    logiflepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), "WebLogfile.log")
    f = open(logiflepath, 'a')
    output = time.strftime("[%d.%m.%Y %H:%M:%S] ") + str(message) + "\n"
    f.write(output)
    f.close()
    print(time.strftime("[%d.%m.%Y %H:%M:%S] ") + str(message))


class ChatCommand:
    def __init__(self, command, description, access_level, callback, args, is_channel_command):
        self.command = command.lower()
        self.original_command = command
        self.description = description
        self.accesslevel = access_level
        self.is_channel_command = is_channel_command
        self.callback = callback
        self.args = args


class Timer:
    def __init__(self):
        self._timer_list = {}
        self._timer_counter = 0

    def start_timer(self, callback, interval, is_single_shot=False, *args):
        self._timer_counter += 1
        self._timer_list[self._timer_counter] = [callback, time_since_epoch()+interval, interval, is_single_shot, args]
        return self._timer_counter

    def remove_timer(self, timer_id):
        if timer_id in self._timer_list:
            self._timer_list.pop(timer_id)
            return True
        return False

    def check_timers(self):
        for i in dict(self._timer_list):
            timer = self._timer_list[i]
            if time_since_epoch() > timer[1]:
                timer[0](*timer[4])
                timer[1] = time_since_epoch() + timer[2]
                if timer[3]:
                    self._timer_list.pop(i)

    @staticmethod
    def get_seconds(seconds):
        return 1000 * seconds

    def reset(self):
        self._timer_list.clear()


class Event:
    def __init__(self, args, data=None):
        self.args = args
        self.data = data
        self.bot = None

    def to_string(self):
        return "[" + str(self.args) + " : " + str(self.data) + "]"

    def __str__(self):
        return self.to_string()

    def __repr__(self):
        return self.to_string()


def starts_with_c_i(string, compare):
    return string.lower().startswith(compare.lower())


def escape(message):
    message = message.replace("\\", "\\\\")
    message = message.replace("/", "\\/")
    message = message.replace(" ", "\\s")
    message = message.replace("|", "\\p")
    message = message.replace("\a", "\\a")
    message = message.replace("\b", "\\b")
    message = message.replace("\f", "\\f")
    message = message.replace("\n", "\\n")
    message = message.replace("\r", "\\r")
    message = message.replace("\t", "\\t")
    message = message.replace("\v", "\\v")
    return message


def unescape(message):
    message = message.replace("\\\\", "\\")
    message = message.replace("\\/", "/")
    message = message.replace("\\s", " ")
    message = message.replace("\\p", "|")
    message = message.replace("\\a", "\a")
    message = message.replace("\\b", "\b")
    message = message.replace("\\f", "\f")
    message = message.replace("\\n", "\n")
    message = message.replace("\\r", "\r")
    message = message.replace("\\t", "\t")
    message = message.replace("\\v", "\v")
    return message


def extract_args(message):
    split = re.split("\s+", message)
    value_map = {}
    for i in split:
        re_match = re.search("(^.*?)=(.*)", i)
        if re_match:
            key = re_match.group(1)
            value = re_match.group(2)
        else:
            key = i
            value = ""
        value_map[key] = unescape(value)
    return value_map


def normalize_message(message):
    ret = []
    split = message.split("|")
    for i in split:
        ret.append(extract_args(i))
    return ret


def time_since_epoch():
    return time.time() * 1000
