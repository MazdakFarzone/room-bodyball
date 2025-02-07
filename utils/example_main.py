from signal import pause

from utils.FSM import GameLogic
from utils.constants import BadEvent, Language

from gpiozero import Button, Device
from gpiozero.pins.pigpio import PiGPIOFactory

# The library called 'pigpio' can handle software debouncing and other features a lot better than the standard library
# hence we set it here so that any further handling of pins through the library 'gpiozero' is handled by 'pigpio'
# Device.pin_factory = PiGPIOFactory()


class TheGame():
    """ Game is created as a class since a lot of it is stateful and easier to handle in this manner """

    def __init__(self):
        self.accept_button_press = False

        self.button_red = Button(2, bounce_time=0.001)
        self.button_green = Button(3, bounce_time=0.001)
        self.button_blue = Button(4, bounce_time=0.001)

        self.button_red.when_pressed = lambda: self.button_pressed(1)
        self.button_green.when_pressed = lambda: self.button_pressed(2)
        self.button_blue.when_pressed = lambda: self.button_pressed(3)

        self.logic = GameLogic(self.on_game_idle, self.on_game_starting, self.on_game_started,
                               self.on_something_went_wrong, self.on_connection_lost, game_length_sec=120)
        
        self.logic.start(debug_mode=True)

    def on_game_idle(self):
        """ Is triggered when game is idle """
        print("GAME: Now in idle mode")

    def on_game_starting(self, members: int, lang: Language):
        """ Is triggered when the game is about to start, also sends the number of people in the group """
        print(f"GAME: Game is starting with {members} people, in {lang.value}")

    def on_game_started(self):
        """ Is triggered when game has started """
        print("GAME: Game is now ready")
        self.accept_button_press = True

    def on_something_went_wrong(self, event: BadEvent):
        """ Is triggered when something bad has happened as described by the parameter 'BadEvent' """
        if event == BadEvent.DOOR_OPENED:
            print("GAME: Bad Event! - Door has opened")
        elif event == BadEvent.THROW_OUT_GROUP:
            print("GAME: Bad Event! - Time to throw out group!")

    def on_connection_lost(self):
        """ Connection was lost to the server """
        print("GAME: Connection is lost, damn")

    def button_pressed(self, number: int):
        #print(f'Button pressed: {str(number)}')
        if self.accept_button_press:
            if number == 1:
                print("GAME: Setting to lose!")
                self.logic.room_lost()
            if number == 2:
                print("GAME: Setting to win!")
                self.logic.room_won()
            if number == 3:
                print("GAME: Setting to win at Level 2")
                # Remember that the game must support it!!
                try:
                    self.logic.room_won(level=2)
                except:
                    print("GAME: Failed to win at level 2, not supported")

            self.accept_button_press = False


# This particular clause runs if we are running this python file with e.g. 'python3 main.py'
if __name__ == "__main__":
    game = TheGame()
    # To prevent the game from exiting, you can replace this with any mainloop such as `tk.mainloop()` for TkInter
    pause()