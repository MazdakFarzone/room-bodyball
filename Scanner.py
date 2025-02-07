from pynput import keyboard
from typing import Callable


class BarcodeScanner:

    s = ""
    started = False

    def on_press(self, key):
        try:
            self.s += key.char
        except AttributeError:
            if key is keyboard.Key.enter:
                #print("Enter received")
                #print("Type: " + str(self.s))
                if self.on_barcode_received is not None:
                    self.on_barcode_received(self.s)
                self.s = ""
        except TypeError:
            # Something is very wrong, resetting
            self.s = ""

    def __init__(self, on_barcode_scan: Callable[[str], None], start_now=True):
        """ Creates a barcode scanner that returns a string in the callback, 
        the user can choose to start the scanner at a later point """
        self.listener = keyboard.Listener(on_press=self.on_press)
        self.on_barcode_received = on_barcode_scan

        # Collect events until released
        if start_now:
            self.listener.start()
            self.started = True

    def start(self):
        if not self.started:
            self.listener.start()
            self.started = True

    def set_on_barcode_received(self, on_barcode_scan: Callable[[str], None]):
        """ If you want to change the callable """
        self.on_barcode_received = on_barcode_scan

    def stop(self):
        if self.started:
            self.listener.stop()
            self.started = False
