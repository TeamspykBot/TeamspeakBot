# coding=utf-8
import pymysql


class MysqlManager:
    def __init__(self):
        self._connection = None
        self._cur = None
        self._host = None
        self._port = None
        self._user = None
        self._password = None
        self._db = None

    def connect_to_db(self, host, port, user, password, db):
        self._host = host
        self._port = port
        self._user = user
        self._password = password
        self._db = db
        try:
            self._connection = pymysql.connect(host=host, port=port, user=user, passwd=password, db=db,
                                               autocommit=True, charset='utf8', cursorclass=pymysql.cursors.DictCursor)
            self._cur = self._connection.cursor()
        except pymysql.MySQLError as e:
            if e.args[0] == 2003:  # Could not connect to database
                print(e.args[1])
                exit()
            else:
                raise

    def execute_query(self, sql_query, args=None):
        try:
            self._cur.execute(sql_query, args)
            return self._cur
        except pymysql.MySQLError as e:
            if e.args[0] in (2006, 2013):  # MYSQL GONE AWAY
                self.connect_to_db(self._host, self._port, self._user, self._password, self._db)
            elif e.args[0] in (1062,):  # DUPLICATE KEY ENTRY
                pass
            else:
                raise

    def add_online_client(self, clid, cldbid, name, remote_ip):
        try:
            self.execute_query("INSERT INTO OnlineClients (`clid`, `cldbid`, `name`, `remote_ip`) "
                               "VALUES (%s, %s, %s, %s);", (str(clid), str(cldbid), str(name), str(remote_ip)))
            return True
        except pymysql.IntegrityError:
            return False

    def remove_online_client(self, clid):
        try:
            self.execute_query("DELETE FROM OnlineClients WHERE `clid` = %s", (str(clid)))
            if self._cur.rowcount > 0:
                return True
            return False
        except pymysql.IntegrityError:
            return False

    def clear_online_clients(self):
        self.execute_query("DELETE FROM OnlineClients")

    def set_client_value(self, cldbid, key, value):
        self.execute_query("REPLACE INTO ClientSettings (cldbid, `key`, value) VALUES (%s, %s, %s);",
                           (int(cldbid), str(key), value))

    def get_client_value(self, cldbid, key, default_value=None):
        ret = self.execute_query("SELECT `value` "
                                 "FROM ClientSettings "
                                 "WHERE cldbid=%s AND `key`=%s", (int(cldbid), str(key))).fetchone()
        if ret is None:
            return default_value
        return ret["value"]

    def get_client_values(self, cldbid):
        ret = self.execute_query("SELECT `key`, `value` FROM ClientSettings WHERE cldbid=%s", (int(cldbid))).fetchall()
        if not ret:
            return {}
        ret = {d["key"]: d["value"] for d in ret}
        return ret

    def get_value(self, key, default_value=None):
        ret = self.execute_query("SELECT `value` FROM Settings WHERE `key`=%s", key).fetchone()
        if ret is None:
            return default_value
        return ret["value"]

    def set_value(self, key, value):
        self.execute_query("REPLACE INTO Settings (`key`, value) VALUES (%s, %s);", (key, value))
