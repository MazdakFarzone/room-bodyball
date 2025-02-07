from typing import Callable
from threading import Timer
from datetime import datetime
from .AudioHandler import AudioHandler, AudioType
from .ServerCommunicator import ServerFinder, ServerCommunicator
from .constants import Access, BadEvent, RoomStatus, GameStatus, DoorStatus, Language, Topics
import os

class GameLogic(object):
    """ The main logic of the Game, handles every boring aspect """

    audio_handler = AudioHandler(f"{os.path.dirname(os.path.realpath(__file__))}{os.path.sep}sounds")
    """ Audio handler (accessible as a member in GameLogic for advanced users) """

    auto_play_background_music = True
    """ Set if you want to start the music yourself instead of automatically """

    # Optional listeners
    __on_connection_lost: Callable[[None], None] = None
    __on_door_opening: Callable[[None], None] = None
    __on_max_time_reached: Callable[[None], None] = None
    __on_shutdown_called: Callable[[None], None] = None


    __status: GameStatus
    __points: None
    __addr: str = ""
    __port: int = 0
    __game_length_sec: float
    __timeout_event = None
    __timeout_event_started: datetime
    
    __debug_thread = None
    __debug_mode = False

    def __init__(self, game_idle: Callable[[None], None], game_starting: Callable[[int, Language], None], game_started: Callable[[None], None],
                 game_went_wrong: Callable[[BadEvent], None],  on_connection_lost: Callable[[None], None] = None, game_length_sec: float = 300.0) -> None:

        self.__game_length_sec = game_length_sec

        self.game_idle = game_idle
        self.game_starting = game_starting
        self.game_started = game_started
        self.game_went_wrong = game_went_wrong
        self.__on_connection_lost = on_connection_lost

        self.__status = GameStatus.BOOTING
        self.communicator = ServerCommunicator(
            self.__server_connected, self.__server_lost, self.__server_config_recieved, self.__server_message_recieved)
        self.finder = ServerFinder(self.__server_found)

    def __server_lost(self):
        print("LOGIC: Server Lost, attempting to search again ...")
        if self.__on_connection_lost is not None:
            self.__on_connection_lost()

        # Search for it again ...
        self.finder.search()

    def __server_found(self, addr, port):
        self.__addr = addr
        self.__port = port
        print("LOGIC: Server found, connecting ...")

        if not self.__debug_mode:
            self.communicator.connect(self.__addr, self.__port)
        else:
            print("LOGIC: Server connected!, requesting config")
            self.__debug_thread = Timer(0.5, self.__server_config_recieved, [True, { 'points': [100, 200, 300]}])
            self.__debug_thread.start()

    def __server_connected(self):
        print("LOGIC: Server connected!, requesting config")
        self.communicator.send_config_request()

    def __server_config_recieved(self, recieved, config):
        if recieved:
            print(f"LOGIC: Config recieved: {config}")
            self.__status = GameStatus.IDLE
            self.__points = config['points']
            self.game_idle()
            self.communicator.send_room_status(RoomStatus.READY.value)

            if self.__debug_mode:
                self.__server_message_recieved("tag_scan_result", {'access': 'success', 'members': 4, 'lang': Language.SWEDISH.value})
                self.__debug_thread = Timer(1, self.__server_message_recieved, ["door_status", { 'info': DoorStatus.DOOR_OPENING_STARTING.value}])
                self.__debug_thread.start()
        else:
            print("LOGIC: Config removed, re-requesting ...")
            self.__status = GameStatus.BOOTING
            self.communicator.send_config_request()
            self.__points = None

    def __server_message_recieved(self, topic, message):
        # Used to override certain stuff
        if Topics.SET_STATUS.value in topic:
            msg = message['access']

            if msg == RoomStatus.PLAY.value:
                if self.__status == GameStatus.ACTIVE:
                    return
                self.__timeout_event = Timer(
                    self.__game_length_sec, self.max_time_reached)
                self.__timeout_event.start()
                self.__timeout_event_started = datetime.now()
                self.__status = GameStatus.ACTIVE
                self.audio_handler.play_background_music()
                self.game_started()

            elif msg == RoomStatus.STOP.value:
                if self.__status == GameStatus.FAILED or self.__status == GameStatus.IDLE:
                    return
                self.__status = GameStatus.FAILED
                self.__timeout_event.cancel()
                self.audio_handler.play_losing_sound()
                self.game_went_wrong(BadEvent(message['reason']))

            elif msg == RoomStatus.RESET.value:
                # Play game over sounds also! to indicate that they should leave the room
                if self.__status == GameStatus.IDLE:
                    return
                self.__status = GameStatus.IDLE
                if self.__timeout_event is not None:
                    self.__timeout_event.cancel()
                self.audio_handler.stop_all_music_and_sound()
                self.audio_handler.play_please_leave_room()
                self.game_went_wrong(BadEvent.THROW_OUT_GROUP)
                self.game_idle()
                self.communicator.send_room_status(RoomStatus.READY.value)
            
            elif msg == RoomStatus.REBOOT.value:
                self.__status = GameStatus.FAILED
                if self.__timeout_event is not None:
                    self.__timeout_event.cancel()
                self.audio_handler.stop_all_music_and_sound()
                self.game_went_wrong(BadEvent.REBOOTING)
            
            elif msg == RoomStatus.SHUTDOWN.value:
                self.__status == GameStatus.FAILED
                if self.__timeout_event is not None:
                    self.__timeout_event.cancel()
                self.audio_handler.stop_all_music_and_sound()
                if self.__on_shutdown_called is not None:
                    self.__on_shutdown_called()
            
            elif msg == RoomStatus.ENDED.value:
                # Game has ended, send message upwards and let the room logic decide
                if self.__status == GameStatus.IDLE:
                    return
                if self.__timeout_event is not None:
                    self.__timeout_event.cancel()
                self.game_went_wrong(BadEvent.GAME_ENDED)

        if Topics.DOOR_STATUS.value in topic:
            info = message['info']
            if info == DoorStatus.IDLING.value and self.__status != GameStatus.IDLE:
                if self.__points == None:
                    # We haven't received our config yet
                    return
                
                self.__status = GameStatus.IDLE
                self.audio_handler.stop_all_music_and_sound()
                self.game_idle()
                self.communicator.send_room_status(RoomStatus.READY.value)

            elif info == DoorStatus.DOOR_OPENING_STARTING.value:
                self.__status = GameStatus.STARTING
                if self.__on_door_opening is not None:
                    self.__on_door_opening()
                
                if self.__debug_mode:
                    self.__debug_thread = Timer(1, self.__server_message_recieved, ["door_status", { 'info': DoorStatus.DOOR_CLOSED_STARTING.value}])
                    self.__debug_thread.start()

            elif info == DoorStatus.DOOR_CLOSED_STARTING.value:
                # Door has closed and is about to start
                self.__timeout_event = Timer(
                    self.__game_length_sec, self.max_time_reached)
                self.__timeout_event.start()
                self.__timeout_event_started = datetime.now()
                self.__status = GameStatus.ACTIVE
                if self.auto_play_background_music:
                    self.audio_handler.play_background_music()
                self.game_started()

            elif info == DoorStatus.DOOR_OPENED_FAILED.value:
                # Opened during the game
                self.__status = GameStatus.FAILED
                if self.__timeout_event is not None:
                    self.__timeout_event.cancel()
                self.audio_handler.play_losing_sound()

                self.game_went_wrong(BadEvent.DOOR_OPENED)

            elif info == DoorStatus.TEAM_STILL_IN_ROOM.value:
                # Play music that they should leave
                self.audio_handler.play_please_leave_room()

        if Topics.SCAN_RESULT.value in topic:
            if message['access'] == Access.SUCCESS.value:
                self.game_starting(
                    message['members'], Language(message['lang']))

        # Debug print
        # print("LOGIC: Recieved topic: " + topic + " - message: " + json.dumps(message))

    def start(self, debug_mode=False):
        """ Start the logic, will find the server, connect and recieve config (must be called)
        
        Optional parameter 'debug_mode' can be set so that it automatically calls room activation after a couple of seconds!
        """
        if not debug_mode:
            self.finder.search()
        else:
            self.__debug_thread = Timer(1, self.__server_found, ["", 0])
            self.__debug_thread.start()
        
        self.__debug_mode = debug_mode

    def set_team_entering_door_opened_listener(self, callback: Callable[[None], None]):
        """ If you want to listen to when a team has opened the door and about to enter, set the callback"""
        self.__on_door_opening = callback

    def handle_max_time_reached(self, callback: Callable[[None], None]):
        """ If you want to manually handle when max time has been reached, set the callable! or else the room is set
            is set to lose when max time is reached, Setting it to "None" will clear it """
        
        self.__on_max_time_reached = callback

    def handle_shutdown_called(self, callback: Callable[[None], None]):
        """ Set callback if you want to do stuff before the os shuts down
        
        """

        self.__on_shutdown_called = callback

    def max_time_reached(self):
        """ Send failure and play the max time reached music """
        print("LOGIC: Max time has been reached, setting game to lost!")

        if self.__on_max_time_reached is not None:
            self.__on_max_time_reached()
        else:
            self.room_lost()

    def set_game_length(self, seconds: int):
        """  Set the current max time for the game.

        Parameters:
            seconds (int): Change the current game length to this value in seconds
        """
        self.__game_length_sec = float(seconds)

        if self.__status == GameStatus.ACTIVE:
            self.__timeout_event.cancel()
        
        self.__timeout_event = Timer(
                    self.__game_length_sec, self.max_time_reached)
        self.__timeout_event.start()

    def add_game_length(self, seconds: int):
        """  Adds seconds to an active game's maximum time (for specific games).

        Parameters:
            seconds (int): The amount of time you want to add
        """
        if self.__status == GameStatus.ACTIVE:
            self.__timeout_event.cancel()

            # How much time is it left? Remember that and add what the user inputted to get the new timeout
            time_diff = self.__game_length_sec - (datetime.now() - self.__timeout_event_started).seconds
            new_game_length = time_diff + seconds

            self.__timeout_event = Timer(new_game_length, self.max_time_reached)
            self.__timeout_event.start()

            self.__timeout_event_started = datetime.now()
    
    def get_game_length(self):
        """  Returns the max game length.

        Returns:
            (int): In seconds
        """
        return int(self.__game_length_sec)

    def room_won(self, level: int = 1):
        """  Set that the team won the room, send the level they won.

        Parameters:
            level (int): Defaults to '1', if you have levels you can correctly set it to whatever level they won
        """
        print(
            f"LOGIC: Room won! at level {str(level)}, reporting at topic 'room_status'")

        # Check if max level was reached and pass it on
        max_level_reached = AudioType.MAX_REACHED if level == len(self.__points) else AudioType.POSITIVE
        self.__timeout_event.cancel()

        if self.__status == GameStatus.ACTIVE:
            self.__timeout_event.cancel()
            self.__status = GameStatus.ENDED
            
            if not self.__debug_mode:
                if level > len(self.__points):
                    raise Exception(
                        "Configuration received from the server does is not compatible with level specified, value is too high")
                self.communicator.send_room_status(RoomStatus.WON.value, level)
                
            self.audio_handler.play_winning_sound(True, int(self.__points[level-1]), max_level_reached)

    def room_lost(self, close_call: bool = False, with_feedback: bool = True):
        """  Set that the team lost the room! 
        
        Parameters:
            close_call (`bool`): Defaults to `False`. If the team was close to a win, set the parameter so that the audio is correct
            with_feedback (`bool`): Defaults to `True`. Skip the voice all together, e.g. when time is up for the team
        """
        
        print(f"LOGIC: Room lost!, reporting at topic 'room_status'")
        
        if self.__status == GameStatus.ACTIVE:
            self.__timeout_event.cancel()
            self.audio_handler.play_losing_sound(run_end_voice=with_feedback, close_call=close_call)
            self.__status = GameStatus.ENDED
        
            if not self.__debug_mode:
                self.communicator.send_room_status(RoomStatus.LOST.value)
    
    def room_reset(self):
        """ Reset the room if it relies on the people staying actively in the room and completing tasks,

            We send this from the room to note that there aren't anyone playing, please reset the room accordingly 
            (e.g. sauna)
        """
        if self.__status == GameStatus.ACTIVE:
            self.room_lost() # Necessary??
            if not self.__debug_mode:
                self.communicator.send_room_status(RoomStatus.RESET.value)
