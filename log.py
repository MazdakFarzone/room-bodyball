class Log(object):

    @classmethod
    def print(self, state: str, message: str):
        print("STATE:", state, "-", message)