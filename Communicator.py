import threading
import serial
from time import sleep
from collections import deque

class SerialCommunication(threading.Thread):

    def __init__(self, callback, message_queue_length=20):
        """ Set the callback to recieve data when it arrives from the Arduino/RPI, use the write method to send something over UART or USB"""
        self.textQueue = deque(maxlen=message_queue_length)
        self.keep_running = False
        self.callback = callback

        threading.Thread.__init__(self)
    
    def __del__(self):
        if self.keep_running:
            self.close()

    def init_serial(self, dev="/dev/ttyACM0", baudrate=19200) -> bool:
        """Starts the serial given the device and baud rate, this must be run to start the background process

        Args:
            dev (`str`, optional): the device path, default is the USB port. Defaults to "/dev/ttyACM0".
            baudrate (`int`, optional): The baud rate of the communication. Defaults to 19200.

        Returns:
            `True`: If init was successful
        """
        if self.keep_running:
            self.close()
        
        try:
            self.ser = serial.Serial(dev, baudrate=baudrate, timeout=1)
            self.ser.flush()
            self.keep_running = True

            self.start()
            return True
        except:
            return False

    def write(self, text:str):
        """Adds the text to the write queue, if the queue is full the oldest message is deleted

        Args:
            text (str): The string that is to be sent
        """

        # If queue is full you will remove from other end! (right)
        text_mod = text + '\n'
        self.textQueue.appendleft(text_mod.encode())

    def close(self):
        """ Close the serial communication """
        self.keep_running = False
        self.ser.flush()
        self.textQueue.clear()
        self.ser.close()
        self.join()
    
    def clear_queue(self):
        """ Cleares the current text queue """
        self.textQueue.clear()

    def run(self):
        """ Is run automatically by the background process! """
        # Needs to sleep for some apparent reason, weird AF
        sleep(2)
        while self.keep_running:
            if self.textQueue is not None and len(self.textQueue) > 0:
                try:
                    self.ser.write(self.textQueue.pop())
                except:
                    pass
            try:
                if self.ser.in_waiting > 0:
                    line = self.ser.readline().decode('utf-8').rstrip()
                    self.callback(line)
            except:
                pass
            
           # sleep(0.01)