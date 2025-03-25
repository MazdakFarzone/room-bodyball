from transitions import Machine, EventData
from transitions.extensions.states import add_state_features, Timeout

from .AudioHandler import AudioHandler, AudioType
from .constants import Access, BadEvent, RoomStatus, DoorStatus, Language, Topics, DoubleRoomType, DoubleRoomStatus
from .ServerCommunicator import ServerFinder, ServerCommunicator
from .GameTimer import GameTimer
from .log import Log

from random import randint
from threading import Timer
from typing import Callable

import os
import tkinter as tk

@add_state_features(Timeout)
class TimeoutMachine(Machine):
    pass


class GameLogic(object):

    # All the states, initial being "find server"
    states = ["init", "idle",
              {"name": "find_server", "timeout": (8 + randint(-2, 2)), "on_timeout": "server_not_found"},
              {"name": "connecting_to_server", "timeout": (15 + randint(-2, 2)), "on_timeout": "server_conn_failed"},
              {"name": "get_config", "timeout": (5 + randint(-1, 3)), "on_timeout": "config_failed"},
              "tag_scanned", "door_open", "active", "closed", "shutting_down", "ended", "ended_feedback"]

    # Transitions, init is required because find_server is not triggered on startup (dummy state required)
    transitions = [
        {"trigger": "start_logic",         "source": "init", "dest": "find_server"},
        {"trigger": "server_found",        "source": "find_server", "dest": "connecting_to_server"},
        {"trigger": "server_not_found",    "source": "find_server", "dest": "find_server"},
        {"trigger": "server_is_connected", "source": "find_server", "dest": "get_config"},
        {"trigger": "server_conn_failed",  "source": "connecting_to_server", "dest": "find_server"},
        {"trigger": "server_connected",    "source": "connecting_to_server", "dest": "get_config"},
        {"trigger": "server_lost",         "source": "*", "dest": "find_server"},
        {"trigger": "config_received",     "source": "get_config", "dest": "active", "conditions": "game_is_active"}, 
        {"trigger": "config_received",     "source": "get_config", "dest": "idle"},
        {"trigger": "config_failed",       "source": "*", "dest": "get_config"},
        {"trigger": "access_granted",      "source": "idle", "dest": "tag_scanned"},
        {"trigger": "game_starting",       "source": "tag_scanned", "dest": "door_open"},
        {"trigger": "game_reset",          "source": "tag_scanned", "dest": "idle"},
        {"trigger": "door_failed",         "source": "door_open", "dest": "ended"},     # Too slow to close
        {"trigger": "game_ended",          "source": "door_open", "dest": "ended"},     # The game/team in question's time ended
        {"trigger": "game_reset",          "source": "door_open", "dest": "idle"},
        {"trigger": "game_active",         "source": "door_open", "dest": "active"},
        {"trigger": "door_failed",         "source": "active", "dest": "ended"},        # Door opened during game
        {"trigger": "game_lost",           "source": "active", "dest": "ended"},
        {"trigger": "game_won",            "source": "active", "dest": "ended"},
        {"trigger": "game_ended",          "source": "active", "dest": "ended"},
        {"trigger": "get_feedback",        "source": "ended", "dest": "ended_feedback"},
        {"trigger": "game_reset",          "source": "active", "dest": "idle"},
        {"trigger": "game_ended",          "source": "ended", "dest": "idle"},
        {"trigger": "game_reset",          "source": "ended", "dest": "idle"},  # They are loitering so much that we have to reset
        {"trigger": "game_won",            "source": "ended_feedback", "dest": "ended"},
        {"trigger": "game_lost",           "source": "ended_feedback", "dest": "ended"},
        {"trigger": "game_reset",          "source": "ended_feedback", "dest": "idle"},
        {"trigger": "shutdown_system",     "source": "*", "dest": "shutdown_state"},
        {"trigger": "reboot_system",       "source": "*", "dest": "reboot_state"},
    ]

    def __init__(self, game_idle: Callable[[None], None], game_starting: Callable[[int, Language], None], game_started: Callable[[None], None],
                 game_went_wrong: Callable[[BadEvent], None],  on_connection_lost: Callable[[None], None] = None, game_length_sec: int = 300, audio_buffer=4096) -> None:
        
        self.game_active = False
        """ Indicates whether the game is active or not, used for moments when the server has disconnected to return to the game state
        """

        """ The main logic of the Game, handles every boring aspect """
        self.audio_handler = AudioHandler(f"{os.path.dirname(os.path.realpath(__file__))}{os.path.sep}sounds", audio_buffer)
        """ Audio handler (accessible as a member in GameLogic for advanced users) """

        self.auto_play_background_music = True
        """ Set if you want to start the music yourself instead of automatically """

        # Optional listeners
        self.__on_connection_lost: Callable[[None], None] = None
        self.__on_door_opening: Callable[[None], None] = None
        self.__on_door_closed: Callable[[None], None] = None
        self.__on_max_time_reached: Callable[[None], None] = None
        self.__on_shutdown_called: Callable[[None], None] = None
        self.__on_double_room_event: Callable[[DoubleRoomStatus], None] = None
        
        self.__points = None
        self.__game_length_sec = game_length_sec
        self.__times_played_please_leave = 0

        # If the main program is running tkinter, we use the mainloops own timer functionality
        self.__game_timer = GameTimer(game_length_sec)
        self.__game_timer.set_callback(self.max_time_reached)

        # Debug specific threads
        self.__debug_thread = None
        self.__debug_mode = False

        self.game_idle = game_idle
        self.game_starting = game_starting
        self.game_started = game_started
        self.game_went_wrong = game_went_wrong
        self.__on_connection_lost = on_connection_lost
        
        self.communicator = ServerCommunicator(
            lambda: self.trigger("server_connected"), self.__cb_lost_server, self.__cb_server_conf_recieved, self.__cb_server_message_received, 
            on_message_other_room = self.__cb_on_message_other_received)
        self.server_finder = ServerFinder(self.__cb_found_server)

        self.machine = TimeoutMachine(model=self, states=GameLogic.states, transitions=GameLogic.transitions,
                                      initial="init", send_event=True, ignore_invalid_triggers=True)

    
    def set_tk_timer(self, tk_object: tk.Tk):
        self.__game_timer.use_tk_as_timer(tk_object)

    def cleanup(self):
        self.server_finder.cleanup()
        self.communicator.disconnect(exiting=True)
    
    # Condition functions as helpers to the FSM
    def game_is_active(self, event):
        return self.game_active

    def time_is_up_callback(self, event):
        return self.__on_max_time_reached != None

    def time_is_up_lost(self, event):
        return self.__on_max_time_reached == None
    

    ### Game Logic ###

    def start(self, debug_mode=False):
        """ Start the logic, will find the server, connect and recieve config (must be called)
        
        Optional parameter 'debug_mode' can be set so that it automatically calls room activation after a couple of seconds!
        """
        if debug_mode:
            self.__debug_thread = Timer(.5, self.__cb_found_server, ["", 0])
            self.__debug_thread.start()
        
        self.__debug_mode = debug_mode

        self.trigger("start_logic")

    def set_team_entering_door_opened_listener(self, callback: Callable[[None], None]):
        """ If you want to listen to when a team has opened the door and about to enter, set the callback"""
        self.__on_door_opening = callback
    
    def set_team_entered_door_closed_listener(self, callback: Callable[[None], None]):
        """ If you want to listen to when a team has closed the door and we are about to start, set the callback"""
        self.__on_door_closed = callback

    def set_double_room_event_listener(self, callback: Callable[[DoubleRoomStatus], None]):
        """ Setting an event listener so you could do special stuff when your double room reports, take action on the returned event!"""
        self.__on_double_room_event = callback

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
            self.game_went_wrong(BadEvent.MAX_TIME_REACHED)
            self.room_lost()

    def set_game_length(self, seconds: int):
        """  Set the current max time for the game.

        Parameters:
            seconds (int): Change the current game length to this value in seconds
        """
        self.__game_length_sec = seconds
        self.__game_timer.set_default_game_time(self.__game_length_sec)

    def add_game_length(self, seconds: int):
        """  Adds seconds to an active game's maximum time (for specific games).

        Parameters:
            seconds (int): The amount of time you want to add
        """
        self.__game_timer.extend_time(seconds)
    
    def get_game_length(self):
        """  Returns the max game length.

        Returns:
            (int): In seconds
        """
        return self.__game_length_sec

    def room_won(self, level: int = 1):
        """  Set that the team won the room, send the level they won.

        Parameters:
            level (int): Defaults to '1', if you have levels you can correctly set it to whatever level they won
        """
        print(
            f"LOGIC: Room won! at level {str(level)}, reporting at topic 'room_status'")
        self.trigger("game_won", lvl=level)
        

    def room_lost(self, close_call: bool = False, with_feedback: bool = True):
        """  Set that the team lost the room! 
        
        Parameters:
            close_call (`bool`): Defaults to `False`. If the team was close to a win, set the parameter so that the audio is correct
            with_feedback (`bool`): Defaults to `True`. Skip the voice all together, e.g. when time is up for the team
        """
        
        print(f"LOGIC: Room lost!, reporting at topic 'room_status'")
        
        self.trigger("game_lost", feedback=with_feedback, close=close_call)
    
    def room_reset(self):
        """ Reset the room if it relies on the people staying actively in the room and completing tasks,

            We send this from the room to note that there aren't anyone playing, please reset the room accordingly 
            (e.g. sauna)
        """
        # if not self.__debug_mode:
        self.trigger("game_reset", send_to_server=True)
            # self.communicator.send_room_status(RoomStatus.RESET.value)
    

    ### Callbacks ###

    def __cb_found_server(self, addr, port):
        Log.print(self.state, "ServerFinder found a valid server !")
        self.trigger("server_found", addr=addr, port=port)

    def __cb_lost_server(self):
        Log.print(self.state, "Lost it!")
        if self.__on_connection_lost is not None:
            self.__on_connection_lost()
        self.trigger("server_lost")

    def __cb_server_message_received(self, topic, message):
        if Topics.SET_STATUS.value in topic:
            msg = message['access']

            if msg == RoomStatus.STOP.value:
                # Force stop or something? pass the reason as well
                self.trigger("game_ended", reason=BadEvent(message['reason']))

            elif msg == RoomStatus.RESET.value:
                # Play game over sounds also! to indicate that they should leave the room
                self.trigger("game_reset", send_to_server=False)
            
            elif msg == RoomStatus.REBOOT.value: 
                self.trigger("reboot_system")
            
            elif msg == RoomStatus.SHUTDOWN.value:
                self.trigger("shutdown_system")
            
            elif msg == RoomStatus.ENDED.value:
                # Game has ended, send message upwards and let the room logic decide
                self.trigger("game_ended", reason=BadEvent.GAME_ENDED)

        if Topics.DOOR_STATUS.value in topic:
            info = message['info']
            if info == DoorStatus.IDLING.value and self.state != "idle":
                if self.__points == None:
                    # We haven't received our config yet
                    return
                
                if self.state != "ended":
                    # Eg. when door has been blipped and no one opened, they just ignored. we just reset
                    self.trigger("game_reset", send_to_server=False)
                else:
                    # People left the room and the door is signaling that its idle now
                    self.trigger("game_ended")

            elif info == DoorStatus.DOOR_OPENING_STARTING.value:
                self.trigger("game_starting")
            
            elif info == DoorStatus.DOOR_CLOSED_STARTING.value:
                # Door has closed, check if we have a callback set
                if self.__on_door_closed is not None:
                    self.__on_door_closed()
                
                if self.__debug_mode:
                    self.__debug_thread = Timer(0.5, self.__cb_server_message_received, ["door_status", { 'info': DoorStatus.ACTIVE.value}])
                    self.__debug_thread.start()

            elif info == DoorStatus.ACTIVE.value:
                # Door has closed and we've entered the active phase
                self.trigger("game_active")

            elif info == DoorStatus.DOOR_OPENED_FAILED.value:
                # Opened during the game
                self.trigger("door_failed")

            elif info == DoorStatus.TEAM_STILL_IN_ROOM.value:
                # Play music that they should leave
                # We keep a count of how many times they've complained about it, We are doing it here so that the sound doesn't
                # become all garbled up when playing half of the please leave the room
                self.__times_played_please_leave +=1
                if self.__times_played_please_leave == 4:
                    self.trigger("game_reset", send_to_server=True, final_sendoff=True)
                else:
                    self.audio_handler.play_please_leave_room(volume=0.5)

        if Topics.SCAN_RESULT.value in topic:
            if message['access'] == Access.SUCCESS.value: 
                # No need for trigger as the server grants us access
                self.trigger("access_granted", members=message['members'], lang=Language(message['lang']))

        # Debug print
        # print("LOGIC: Recieved topic: " + topic + " - message: " + json.dumps(message))

    def __cb_on_message_other_received(self, topic, msg):
        type = self.communicator.get_room_type()
        slave = self.communicator.is_double_room_slave()
        #print(f"LOGIC: Other room message - topic: {topic}, - msg: {msg}")
        if self.__on_double_room_event is None:
            raise Exception("Event listener not set for double room events!! cannot proceed")

        if Topics.ROOM_STATUS.value in topic:
            other_room_status = msg["status"]
            
            if other_room_status == RoomStatus.LOST.value and slave and self.state == 'active':
                if type == DoubleRoomType.COMPETITION:
                    self.__on_double_room_event(DoubleRoomStatus.TEAM_WON)
                elif type == DoubleRoomType.COOPERATIVE:
                    self.__on_double_room_event(DoubleRoomStatus.TEAM_LOST)

            elif other_room_status == RoomStatus.WON.value and slave and self.state == 'active':
                if type == DoubleRoomType.COMPETITION:
                    self.__on_double_room_event(DoubleRoomStatus.TEAM_LOST)
                elif type == DoubleRoomType.COOPERATIVE:
                    self.__on_double_room_event(DoubleRoomStatus.TEAM_WON)
                    
            elif other_room_status == RoomStatus.RESET.value:
                if type == DoubleRoomType.COMPETITION and self.state == 'active':
                    self.__on_double_room_event(DoubleRoomStatus.TEAM_WON)
                elif type == DoubleRoomType.COOPERATIVE:
                    self.trigger("game_reset")

        elif Topics.DOOR_STATUS.value in topic:
            other_door_info = msg['info']

            if other_door_info == DoorStatus.DOOR_OPENED_FAILED.value and self.state == 'active':
                if type == DoubleRoomType.COMPETITION:
                    self.__on_double_room_event(DoubleRoomStatus.TEAM_WON)
                elif type == DoubleRoomType.COOPERATIVE:
                    self.__on_double_room_event(DoubleRoomStatus.TEAM_LOST)
            
            elif other_door_info == DoorStatus.TEAM_STILL_IN_ROOM.value and self.state != 'ended':
                # If we are in ended as well we are perhaps taking care of this already, no need to be nagging
                self.__times_played_please_leave +=1
                if self.__times_played_please_leave == 4:
                    self.audio_handler.play_please_leave_room(last_statement=True, volume=0.8)
                    self.__times_played_please_leave = 0
                else:
                    self.audio_handler.play_please_leave_room(volume=0.5)

    def __cb_server_conf_recieved(self, success, config: dict):
        if success:
            print(f"LOGIC: Config recieved: {config}")

            # We are only picking up the points from the config atm.
            self.__points = config['points']

            if self.__debug_mode:
                self.machine.set_state("get_config")
            self.trigger("config_received")

        else:
            print("LOGIC: Config removed, re-requesting ...")
            self.trigger("config_failed")

    ### State logic ###

    # find_server

    def on_enter_find_server(self, event):
        Log.print(self.state, "Enter find_server")

        if self.__debug_mode:
            # Do nothing as we have a timer running for finding:
            return
        
        # Are we connected??
        if self.communicator.is_connected():
            self.trigger("server_is_connected")
        else:    
            event_name = str(event.event.name)
            
            # If our the server connection fails, we force our search to find a new IP and port
            forced_search = event_name == 'server_conn_failed'

            self.server_finder.search(forced_search)

    # connecting_to_server
    def on_enter_connecting_to_server(self, event):
        Log.print(self.state, "Enter connecting_to_server")

        addr = event.kwargs.get('addr', '')
        port = event.kwargs.get('port', 0)

        Log.print(self.state, "Connecting to: " + str(addr) +
                  " : " + str(port) + " now connecting ...")

        if not self.__debug_mode:
            self.communicator.connect(addr, port)
        else:
            print("LOGIC: Server connected!, requesting config")
            self.__debug_thread = Timer(1.5, self.__cb_server_conf_recieved, [True, { 'points': [100, 200, 300]}])
            self.__debug_thread.start()
        

    # get_config
    def on_enter_get_config(self, event):
        Log.print(self.state, "Enter get_config")
        self.__points = None
        self.communicator.send_config_request()

    # idle
    def on_enter_idle(self, event: EventData):
        Log.print(self.state, "Enter idle from: " + str(event.event.name))
        self.audio_handler.stop_all_music_and_sound()
        self.__times_played_please_leave = 0
        
        if str(event.event.name) == "game_reset":
            send_to_server = event.kwargs.get("send_to_server")
            fucking_leave = event.kwargs.get("final_sendoff", False)
            if send_to_server: 
                # We triggered the reset ourselves, e.g. like in sauna, no need for extra callbacks and sound
                if not self.__debug_mode:
                    self.communicator.send_room_status(RoomStatus.RESET.value)
                # We have tried to send them from the room, but they won't leave, resetting now!
                if fucking_leave:
                    self.audio_handler.play_please_leave_room(last_statement=True, volume=0.8)
                    self.game_went_wrong(BadEvent.THROW_OUT_GROUP)

        self.communicator.send_room_status(RoomStatus.READY.value)
        self.game_idle()

        if self.__debug_mode:
            self.__cb_server_message_received("tag_scan_result", {'access': 'success', 'members': 4, 'lang': Language.SWEDISH.value})
            self.__debug_thread = Timer(1, self.__cb_server_message_received, ["door_status", { 'info': DoorStatus.DOOR_OPENING_STARTING.value}])
            self.__debug_thread.start()

    
    # tag_scanned
    def on_enter_tag_scanned(self, event):
        Log.print(self.state, "Enter tag_scanned")
        members = event.kwargs.get("members")
        language = event.kwargs.get("lang")

        self.game_starting(members, language)

    # door_open
    def on_enter_door_open(self, event):
        Log.print(self.state, "Enter door_open")
        
        if self.__on_door_opening is not None:
            self.__on_door_opening()
        
        if self.__debug_mode:
            self.__debug_thread = Timer(1, self.__cb_server_message_received, ["door_status", { 'info': DoorStatus.DOOR_CLOSED_STARTING.value}])
            self.__debug_thread.start()

    # active
    def on_enter_active(self, event):
        Log.print(self.state, "Enter active")
        self.__game_timer.start(self.__game_length_sec)
        
        if self.auto_play_background_music:
            self.audio_handler.play_background_music()
        
        self.game_started()
        self.game_active = True

    # ended
    def on_enter_ended(self, event: EventData):
        Log.print(self.state, "Enter ended - from: " + str(event.event.name))
        self.game_active = False
        self.__game_timer.cancel()

        # You opened the door and ended the game, or held the door open for too long
        # Will occur if the team aren't closing the door fast enough!
        if (str(event.event.name) == 'door_failed'):
            self.audio_handler.play_losing_sound()
            self.game_went_wrong(BadEvent.DOOR_OPENED)
        
        elif (str(event.event.name) == 'game_ended'):
            reason: BadEvent = event.kwargs.get("reason")
            print("Reason: " + reason.name)
            if reason == BadEvent.GAME_ENDED:
                self.trigger("get_feedback")
            else:
                self.audio_handler.play_losing_sound()
                self.game_went_wrong(reason)

        elif (str(event.event.name) == 'game_won'):
            level = event.kwargs.get("lvl")
            
            if not self.__debug_mode:
                if level > len(self.__points):
                    raise Exception(
                        "Configuration received from the server does is not compatible with level specified, value is too high")
                self.communicator.send_room_status(RoomStatus.WON.value, level)
                
            max_level_reached = AudioType.MAX_REACHED if level == len(self.__points) else AudioType.POSITIVE
            self.audio_handler.play_winning_sound(True, int(self.__points[level-1]), max_level_reached)

        elif (str(event.event.name) == 'game_lost'):
            with_feedback = event.kwargs.get("feedback")
            close_call = event.kwargs.get("close")
            self.audio_handler.play_losing_sound(run_end_voice=with_feedback, close_call=close_call)

            if not self.__debug_mode:
                self.communicator.send_room_status(RoomStatus.LOST.value)
    
    # ended_feedback
    def on_enter_ended_feedback(self, event):
        Log.print(self.state, "Enter ended_feedback")
        self.game_went_wrong(BadEvent.GAME_ENDED)

    # shutting down
    def on_enter_shutting_state(self, event):
        Log.print(self.state, "Shutting down entire system")
        self.__game_timer.cancel()
        if self.__on_shutdown_called is not None:
            self.__on_shutdown_called()
    
    # shutting down
    def on_enter_reboot_state(self, event):
        Log.print(self.state, "Shutting down entire system")
        self.__game_timer.cancel()
        self.audio_handler.stop_all_music_and_sound()
        self.game_went_wrong(BadEvent.REBOOTING)

