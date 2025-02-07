from ServerCommunicator import ServerFinder, ServerCommunicator
from constants import Topics, RoomStatus
import os
from signal import pause
from threading import Timer


class SystemConditionLogic:
    """Handles shutdown and reboot logic by connecting separately to the mqtt server\n
    The MQTT server sends a REBOOT or a SHUTDOWN request and this service will handle it. This is done circumvent locks in the game making reboots/shutdowns hard to do.
    \nThis service will connect to the MQTT server as a "spy" to avoid updating any health monitoring metrics in the server
    """

    def __init__(self):
        self.communicator = ServerCommunicator(
            self.__server_connected, self.__server_lost, self.__server_config_recieved, self.__server_message_recieved, True)
        self.finder = ServerFinder(self.__server_found)
        self.finder.search()

        # Shutdown / Reboot - delay
        self.delay_in_seconds = 3
        self.timer: Timer = None

    def __server_found(self, addr, port):
        print("SHUTDOWN-LOGIC: Server found!, connecting ...")
        self.communicator.connect(addr, port)

    def __server_connected(self):
        print("SHUTDOWN-LOGIC: Connected!")
        self.communicator.send_config_request()

    def __server_lost(self):
        print("SHUTDOWN-LOGIC: Lost server")

        # Search for it again ...
        self.finder.search()

    def __server_config_recieved(self, recieved: bool, config: dict):
        if recieved:
            print("SHUTDOWN-LOGIC: Now armed and active!")
        else:
            print("SHUTDOWN-LOGIC: Room removed, sending config request again!")
            self.communicator.send_config_request()


    def shutdown_system(self):
        """ Shut down the raspberry pi by running the shutdown script """
        # Is run as root from the systemd service, only way possible
        os.system("shutdown now")

    def reboot_system(self):
        # Is run as root from the systemd service, only way possible
        os.system("reboot")

    def __server_message_recieved(self, topic: str, message: str):
        if Topics.SET_STATUS.value in topic:
            msg = message['access']

            if msg == RoomStatus.REBOOT.value:
                self.timer = Timer(self.delay_in_seconds, self.reboot_system)
                self.timer.start()
            elif msg == RoomStatus.SHUTDOWN.value:
                self.timer = Timer(self.delay_in_seconds, self.shutdown_system)
                self.timer.start()
                

if __name__ == "__main__":
    logic = SystemConditionLogic()
    pause()
