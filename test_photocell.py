from signal import pause
from gpiozero import DigitalInputDevice
from settings import PINS

def triggered(text):
    print(f"TRIGGERED, Pin: {text}")

devs = []

for p in PINS.photocells_list:
    dev = DigitalInputDevice(p, pull_up=True, bounce_time=0.01)
    dev.when_deactivated = lambda t=p: triggered(t)
    devs.append(dev)


try:
    pause()

except:
    pass