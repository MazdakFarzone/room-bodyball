from signal import pause
from transitions import Machine


class FSM(object):
    states = ["start", "stuff"]

    transitions =  [
        {"trigger": "more", "source": "start", "dest": "stuff"},
        {"trigger": "redo", "source": "stuff", "dest": "start"}
    ]

    def __init__(self):
        self.machine = Machine(model=self, transitions=self.transitions, states=self.states, initial="start", send_event=True)

    def on_enter_start(self, event):
        print("STATE: on_enter_start")
    
    def on_exit_start(self, event):
        print("STATE: on_exit_start - " + self.state)
    
    def on_enter_stuff(self, event):
        print("STATE: on_enter_stuff: " + str(event.kwargs.get("level")) + " - s: " + str(event.kwargs.get("s")))

    def on_exit_stuff(self, event):
        print("STATE: on_exit_stuff")


f = FSM()
f.trigger("more", level=1, s=2)
try:
    pause()
except:
    pass

