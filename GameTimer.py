import threading
import tkinter as Tk
from typing import Callable

from datetime import datetime

class GameTimer:
    def __init__(self, game_time_seconds: int):
        """
        Initialize the timer. 
        - If `use_tk` is None, it uses threading.Timer.
        - If `use_tk` is a Tkinter `Tk` object, it uses `after`.
        :param use_tk: Tkinter object if using Tkinter based timer.
        """
        
        self._tk_obj = None
        self._timer = None
        self._is_running = False
        self._timeout_event_started: datetime = None
        self._time_in_seconds = game_time_seconds

    def start(self, override_seconds: int = None):
        """Starts the timer."""
        if self._is_running:
            return

        self._timeout_event_started = datetime.now()
        seconds = self._time_in_seconds if override_seconds is None else override_seconds
        self._is_running = True

        if self._tk_obj is not None:

            self._start_tk_timer(seconds)
        else:
            self._start_threading_timer(seconds)
    
    def set_callback(self, callback: Callable[[None], None]):
        self.callback = callback
    
    def use_tk_as_timer(self, tk_object: Tk.Tk):
        """ Use tk instead, stops current timer too """
        self.cancel()
        self._tk_obj = tk_object

    def _start_threading_timer(self, seconds: int):
        """Starts a threading.Timer based timer."""
        self._timer = threading.Timer(seconds, self._time_up)
        self._timer.start()

    def _start_tk_timer(self, seconds: int):
        """Starts a Tkinter-based timer using `after`."""
        self._timer = self._tk_obj.after(int(seconds * 1000), self._time_up)

    def _time_up(self):
        """Callback for when time is up."""
        self._is_running = False
        if self.callback:
            self.callback()

    def cancel(self):
        """Cancels the timer if it's running."""
        if self._timer:
            if self._tk_obj is not None:
                self._tk_obj.after_cancel(self._timer)
            else:
                self._timer.cancel()
            self._is_running = False

    def set_default_game_time(self, game_time_seconds: int):
        """
        Sets the game time.

        If the timer is still running, it cancels it and starts it again with the new game time.
        :param game_time_seconds: The new game time in seconds
        """
        self._time_in_seconds = game_time_seconds

        if self._is_running:
            self.cancel()
            self.start()

    def extend_time(self, extra_seconds: int):
        """
        Extends the current timer.

        If the timer is still running, it cancels it and starts it again with the extended time.
        :param extra_seconds: Extra seconds to add to the timer.
        """
        if self._is_running:
            self.cancel()

            time_diff = self._time_in_seconds - (datetime.now() - self._timeout_event_started).seconds
            print("Extended to: " + str(time_diff + extra_seconds))
            self.start(time_diff + extra_seconds)

    def is_running(self):
        """Returns whether the timer is currently running."""
        return self._is_running
