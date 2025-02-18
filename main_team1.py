from signal import pause

from utils.FSM import GameLogic
from utils.constants import BadEvent, Language

from gpiozero import DigitalInputDevice
from settings import PINS, GameSettings as GS, Team, Audio

# The library called 'pigpio' can handle software debouncing and other features a lot better than the standard library
# hence we set it here so that any further handling of pins through the library 'gpiozero' is handled by 'pigpio'
# Device.pin_factory = PiGPIOFactory()


class TheGame():
    """ Game is created as a class since a lot of it is stateful and easier to handle in this manner """

    def __init__(self):
        self.logic = GameLogic(self.on_game_idle, self.on_game_starting, self.on_game_started,
                               self.on_something_went_wrong, self.on_connection_lost, game_length_sec=1000)
        
        self.logic.start(debug_mode=GS.debug_mode)

    def on_game_idle(self):
        """ Is triggered when game is idle """
        print("GAME: Now in idle mode")

    def on_game_starting(self, members: int, lang: Language):
        """ Is triggered when the game is about to start, also sends the number of people in the group """
        print(f"GAME: Game is starting with {members} people, in {lang.value}")

    def on_game_started(self):
        """ Is triggered when game has started """
        print("GAME: Game is now ready")

    def on_something_went_wrong(self, event: BadEvent):
        """ Is triggered when something bad has happened as described by the parameter 'BadEvent' """
        print(f"GAME: Something went wrong!: {event.name}")

    def on_connection_lost(self):
        """ Connection was lost to the server """
        print("GAME: Connection is lost, damn")

# This particular clause runs if we are running this python file with e.g. 'python3 main.py'
if __name__ == "__main__":
    game = TheGame()
    # To prevent the game from exiting, you can replace this with any mainloop such as `tk.mainloop()` for TkInter
    pause()