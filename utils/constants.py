from enum import Enum

class Topics(Enum):
    SET_STATUS = "set_status"
    DOOR_STATUS = "door_status"
    ROOM_STATUS = "room_status"
    SCAN_RESULT = "tag_scan_result"

class BadEvent(Enum):
    """ Describing something bad that has happened """
    DOOR_OPENED = 1
    THROW_OUT_GROUP = 2
    TEAM_STILL_IN_ROOM = 3
    REBOOTING = 4
    GAME_ENDED = 5
    MAX_TIME_REACHED = 6

class RoomStatus(Enum):
    """ Status of the room that is send to topic 'room status'"""
    PLAY = "play"
    STOP = "stop"
    RESET = "reset"
    CLOSE = "close"
    OPEN = "open"
    WON = "won"
    LOST = "lost"
    REBOOT = "reboot"
    SHUTDOWN = "shutdown"
    READY = "ready"
    ENDED = "game ended"

class DoubleRoomType(Enum):
    """ What type of combined room is it? React accordingly"""
    COMPETITION = "competitive"
    COOPERATIVE = "cooperative"

class DoubleRoomStatus(Enum):
    """ Handle events based on what happened for the other room, You have to take action on these events """
    TEAM_WON = 1
    TEAM_LOST = 2

class DoorStatus(Enum):
    """ Extened info coming from the door is described here """
    DOOR_OPENING_STARTING = "Door Opening (Starting)"
    DOOR_CLOSED_STARTING = "Door Closed (Starting)"
    ACTIVE = "Game active"
    DOOR_OPENED_FAILED = "Door Opened (Failed)"
    TEAM_STILL_IN_ROOM = "Team loitering"
    CLOSED = "Closed"
    SERVICE_IN_PROGRESS = "Service mode"
    IDLING = "Idle"

class GameStatus(Enum):
    """ Describing the current Game status """
    BOOTING = 0
    IDLE = 1
    STARTING = 2
    ACTIVE = 3
    FAILED = 4
    ENDED = 5

class Language(Enum):
    """ The language the team wants to play in """
    SWEDISH = "Swedish"
    ENGLISH = "English"

class Access(Enum):
    SUCCESS = "success"
    FAILED = "denied"
    ADMIN = "admin"
