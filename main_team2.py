from signal import pause

from utils.FSM import GameLogic
from utils.constants import BadEvent, Language, DoubleRoomStatus

from gpiozero import DigitalInputDevice
from settings import PINS, GameSettings as GS, Team, Audio

from threading import Timer

# The library called 'pigpio' can handle software debouncing and other features a lot better than the standard library
# hence we set it here so that any further handling of pins through the library 'gpiozero' is handled by 'pigpio'
# Device.pin_factory = PiGPIOFactory()


class TheGame():
    """ Game is created as a class since a lot of it is stateful and easier to handle in this manner """

    def __init__(self):
        self.accept_goal = False
        self.sudden_death = False
        self.scores = [0, 0] # Team 1 at pos 0, team 2 at pos 1
        self.devs = []
        self.intro_timer: Timer = None

        for setup_list in PINS.photocells_list:
            dev = DigitalInputDevice(setup_list['pin'], pull_up=True, bounce_time=0.01)
            dev.when_deactivated = lambda team=setup_list['team']: self.on_score(team)
            self.devs.append(dev)

        self.logic = GameLogic(self.on_game_idle, self.on_game_starting, self.on_game_started,
                               self.on_something_went_wrong, self.on_connection_lost, game_length_sec=GS.game_time)
        
        self.logic.auto_play_background_music = False
        self.logic.audio_handler.change_ending_volume(0.7)
        self.logic.handle_max_time_reached(self.max_time_reached)
        self.logic.set_double_room_event_listener(self.on_other_room_reported)
        self.logic.start(debug_mode=GS.debug_mode)
    
    def on_score(self, team: Team):
        if not self.accept_goal:
            return
        
        if GS.debug_mode:
            print(f"SCORE: Got score from: {team.name}")
        
        # Which side does the photocell belong to?
        if team == Team.TEAM1:
            audio_file = Audio.team1_score
            self.scores[1] += 1 # Set the score correct
        else:
            audio_file = Audio.team2_score
            self.scores[0] += 1
        
        if self.sudden_death:
            self.max_time_reached()
        else:
            self.logic.audio_handler.play_custom_sound_now(audio_file, Audio.path, 2, 1.2)

        
    def max_time_reached(self):
        if self.scores[0] > self.scores[1]:
            self.logic.room_lost()
            self.logic.audio_handler.stop_all_music_and_sound()
            self.logic.audio_handler.play_custom_sound_now(Audio.team1_won, Audio.path, 1, 1.2)
            self.accept_goal = False
        
        elif self.scores[1] > self.scores[0]:
            self.logic.room_won()
            self.logic.audio_handler.stop_all_music_and_sound()
            self.logic.audio_handler.play_custom_sound_now(Audio.team2_won, Audio.path, 1, 1.2)
            self.accept_goal = False

        else:
            self.logic.audio_handler.set_custom_sound(Audio.sudden_death, directory=Audio.path)
            self.logic.audio_handler.play_custom_sound()
            self.sudden_death = True

    def on_game_idle(self):
        """ Is triggered when game is idle """
        print("GAME: Now in idle mode")

    def on_game_starting(self, members: int, lang: Language):
        """ Is triggered when the game is about to start, also sends the number of people in the group """
        print(f"GAME: Game is starting with {members} people, in {lang.value}")
        self.accept_goal = False

    def on_game_started(self):
        """ Is triggered when game has started """
        print("GAME: Game is now ready")
        intro_time = self.logic.audio_handler.play_custom_sound_now(Audio.ready_go, Audio.path, 1, 1)
        self.intro_timer = Timer(intro_time, self.intro_time_finished)
        self.intro_timer.start() 
    
    def intro_time_finished(self):
        self.scores = [0, 0]
        self.sudden_death = False
        self.accept_goal = True
        self.intro_timer = None

    def on_something_went_wrong(self, event: BadEvent):
        """ Is triggered when something bad has happened as described by the parameter 'BadEvent' """
        if event != BadEvent.THROW_OUT_GROUP:
            # We want them to hear the resetting room sound
            self.logic.audio_handler.stop_all_music_and_sound()
        
        if self.intro_timer is not None:
            self.intro_timer.cancel()

        if event == BadEvent.GAME_ENDED:
            self.max_time_reached()
        elif event == BadEvent.DOOR_OPENED:
            self.logic.audio_handler.set_custom_sound(Audio.team1_won, directory=Audio.path)
            self.logic.audio_handler.play_custom_sound()
            self.accept_goal = False
        else:
            self.accept_goal = False

    def on_other_room_reported(self, event: DoubleRoomStatus):
        """ Triggered when other room has reported the 'event', we have to act on this!"""
        if self.intro_timer is not None:
            self.intro_timer.cancel()

        if event == DoubleRoomStatus.TEAM_WON:
            self.logic.room_won()
            audio_file = Audio.team2_won

        elif event == DoubleRoomStatus.TEAM_LOST:
            self.logic.room_lost()
            audio_file = Audio.team1_won
        
        self.logic.audio_handler.stop_all_music_and_sound()
        self.logic.audio_handler.play_custom_sound_now(audio_file, Audio.path, 1, 1.2)

    def on_connection_lost(self):
        """ Connection was lost to the server """
        print("GAME: Connection is lost, damn")

# This particular clause runs if we are running this python file with e.g. 'python3 main.py'
if __name__ == "__main__":
    game = TheGame()
    # To prevent the game from exiting, you can replace this with any mainloop such as `tk.mainloop()` for TkInter
    pause()