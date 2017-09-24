# coding=utf-8
class Query:
    def __init__(self, callback, data, text, err_callback):
        self.callback = callback
        self.data = data
        self.text = text
        self.errCallback = err_callback
        self.completed = False

    def to_string(self):
        return "{0}|{1}|{2}|{3}|{4}".format(self.text, self.data, self.callback, self.errCallback, self.completed)

    def __str__(self):
        return self.to_string()

    def __repr__(self):
        return self.to_string()


class QueryTracker:
    def __init__(self):
        self._queryList = []

    def add_query(self, query):
        self._queryList.append(query)

    def complete_last_query(self):
        for query in self._queryList:
            if not query.completed:
                query.completed = True
                return query

    def get_last_uncompleted_query(self):
        for query in self._queryList:
            if not query.completed:
                return query

    def to_string(self):
        return str(self._queryList)

    def clean_up(self):
        self._queryList[:] = [x for x in self._queryList if not x.completed]

    def reset(self):
        self._queryList.clear()

    def __str__(self):
        return self.to_string()

    def __repr__(self):
        return self.to_string()
