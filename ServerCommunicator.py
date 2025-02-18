from random import randint
from zeroconf import IPVersion, ServiceBrowser, ServiceStateChange, Zeroconf
from typing import Callable

import paho.mqtt.client as mqtt
from secrets import choice
import string
import json

from threading import Timer
from .constants import DoubleRoomType

import netifaces
import socket

from apscheduler.schedulers.background import BackgroundScheduler


class ServerFinder(object):

    services = ["_team._tcp.local."]

    permanent_server_ip = "192.168.1.200"
    permanent_server_port = 51000

    def __init__(self, on_server_found: Callable[[str, int], None]):
        self.__on_server_found = on_server_found

        self.__server_found = False
        self.__browser = None
        self.__no_times_searched = 0

        self.__check_online_thread = None

        self.__found_ip = None
        self.__found_port = None

    def search(self, forced=False):
        # Cleanup if this is the second time around
        if self.__browser is not None:
            print("ServerFinder: Browser still active, restarting the browser!")
            self.__browser.cancel()
            self.__zeroconf.close()
            self.__browser = None

        if self.__check_online_thread is not None:
            print("ServerFinder: The online checker is not None, canceling it")
            self.__check_online_thread.cancel()
            self.__check_online_thread = None

        # Start up (or over again), setting up a new browser will cause the callback to be called!
        # Since the removed callback isn't working, we are just recreating the browser everytime something fails, and let the
        # mqttclient handle disconnect events
        if forced:
            self.__server_found = False
            self.__found_ip = None
            self.__found_port = None
        
        if self.__server_found:
            self.__on_server_found(self.__found_ip, self.__found_port)
            return

        if self.__get_ip_addr() == "Unknown IP":
            print("ServerFinder: Unknown IP, restarting ...")
            self.__check_online_thread = Timer(0.5, self.search)
            self.__check_online_thread.start()
        elif self.__no_times_searched <= 5:
            self.__zeroconf = Zeroconf(ip_version=IPVersion.V4Only)
            self.__browser = ServiceBrowser(self.__zeroconf, ServerFinder.services, handlers=[
                self.on_service_state_change])
            self.__no_times_searched += 1
        else:
            print("ServerFinder: Forcing permanent fallback IP ...")
            self.__on_server_found(
                self.permanent_server_ip, self.permanent_server_port)
            self.__no_times_searched = 0  # Resetting so that we search again just in case

    def on_service_state_change(self, zeroconf: Zeroconf, service_type: str, name: str, state_change: ServiceStateChange
                                ) -> None:
        print(
            f"Service {name} of type {service_type} state changed: {state_change}")

        if state_change == ServiceStateChange.Added:
            info = zeroconf.get_service_info(service_type, name)
            if info:
                addr = info.parsed_scoped_addresses(version=IPVersion.V4Only)
                self.__found_ip = addr[0]
                self.__found_port = info.port
                self.__on_server_found(self.__found_ip, self.__found_port)
                self.__server_found = True

    def is_server_found(self) -> bool:
        return self.__server_found

    def cleanup(self):
        if self.__browser is not None:
            self.__browser.cancel()
            self.__browser = None
        if self.__check_online_thread is not None:
            self.__check_online_thread.cancel()
        self.__zeroconf.close()
        
        self.__server_found = False
        self.__found_ip = None
        self.__found_port = None

    def __get_ip_addr(self):
        ip = "Unknown IP"
        try:
            ip = str(netifaces.ifaddresses('eth0')[2][0]['addr'])
        except KeyError:
            try:
                ip = str(netifaces.ifaddresses('wlan0')[2][0]['addr'])
                ip += " (WiFi)"
            except KeyError:
                pass
        return ip



class ServerCommunicator(object):

    username = "teamification"
    password = "mqttServerPassword"
    room = "-1"
    ping_job = None

    config_job = None
    config_recieved = False
    
    connect_job = None
    
    __loop_started = False
    __disconnect_handled = False


    def __init__(self, on_connect: Callable[[None], None], on_server_lost: Callable[[None], None], 
                 on_config: Callable[[bool, dict], None], on_message: Callable[[str, str], None],
                 is_a_spy: bool = False, on_message_other_room: Callable[[str, str], None] = None
                 ):
        """Init the Server communicator to talk with the MQTT Server

        Args:
            `on_connect` (Callable[[None], None]): connection callback
            `on_server_lost` (Callable[[None], None]): server lost callback
            `on_config` (Callable[[bool, dict], None]): game config received callback
            `on_message` (Callable[[str, str], None]): message from the server received callback
            `is_a_spy` (`bool`, optional): Ask the server to not update room health/monitor with this connection. Defaults to `False`, 
        """
        self.message_callback = on_message
        self.message_from_other_callback = on_message_other_room
        self.connect_callback = on_connect
        self.config_callback = on_config
        self.disconnect_callback = on_server_lost
        self.is_a_spy = is_a_spy

        self.room_other = None
        
        self.macaddress = str(netifaces.ifaddresses('eth0')[
                              netifaces.AF_LINK][0]['addr'])

        clientid = "Room_" + self.macaddress + "_" + \
            "".join([choice(string.ascii_lowercase + string.digits)
                    for _ in range(6)])
        
        self.mqttclient = mqtt.Client(client_id=clientid)

        self.mqttclient.on_connect = self.on_connect_event
        self.mqttclient.on_disconnect = self.on_disconnected
        self.mqttclient.on_message = self.on_message_received
        self.mqttclient.username_pw_set(self.username, password=self.password)

        self.scheduler = BackgroundScheduler(timezone="Europe/Stockholm")
        self.scheduler.start()

    def __del__(self):
        self.disconnect(True)
        #self.__set_loop(False)
        self.scheduler.shutdown()

    def __set_loop(self, start: bool):
        if start and not self.__loop_started:
            self.mqttclient.loop_start()
            self.__loop_started = True
        
        elif not start and self.__loop_started:
            self.mqttclient.loop_stop()
            self.__loop_started = False

    def connect(self, addr: str, port: int):
        self.__remove_connect_job()
        self.connect_job = self.scheduler.add_job(
            self.__connect_job, 'interval', seconds=5, args=[addr, port], jitter=2)
    
    def is_connected(self) -> bool:
        return self.mqttclient.is_connected()
    
    def __connect_job(self, addr: str, port: int):
        self.disconnect()
        try:
            self.mqttclient.connect(addr, port)
            self.__set_loop(True)
        except:
            # Something went wrong, notifying the user
            self.__remove_connect_job()
            self.disconnect_callback()
    
    def __remove_connect_job(self):
        if self.connect_job != None:
            self.connect_job.remove()
            self.connect_job = None

    def disconnect(self, avoid_callback=False):
        if self.is_connected():
            try:
                self.mqttclient.disconnect()
            except:
                pass
            
        self.__set_loop(False)
        self.__disconnect_handled = avoid_callback

    def send_room_status(self, message, level: int = None):
        payload = {"status": message,
                   "mac": self.macaddress, "room": self.room}
        if level is not None:
            payload["level"] = level

        self.mqttclient.publish("room/" + self.room +
                                "/room_status", json.dumps(payload), qos=2)

    def send_config_request(self):
        self.__remove_config_job()
        self.config_recieved = False
        self.__send_config_request_job()
        self.config_job = self.scheduler.add_job(
            self.__send_config_request_job, 'interval', seconds=4, jitter=2)

    def __send_config_request_job(self):
        if not self.config_recieved:
            ip = self.__get_ip_addr()

            message = {"mac": self.macaddress, "type": "room", "ip": ip, "hostname": socket.gethostname(),
                       "spy": self.is_a_spy
                       }
            self.mqttclient.publish(
                "config/" + self.macaddress + "/request", json.dumps(message), qos=2)
        else:
            self.config_recieved = True
            self.__remove_config_job()

    def __remove_config_job(self):
        if self.config_job != None:
            self.config_job.remove()
            self.config_job = None
    
    def on_disconnected(self, client, userdata, rc):
        self.__remove_config_job()
        self.__remove_ping_job()

        if not self.__disconnect_handled:
            self.disconnect()
            self.disconnect_callback()

    def on_message_received(self, client, userdata, msg):
        decoded_message = json.loads(msg.payload.decode())
        other_room = False

        if "config" in msg.topic:
            self.on_config_received(decoded_message)
            return

        if self.room_other and f"/{self.room_other}/" in msg.topic:
            other_room = True

        if not other_room:
            self.message_callback(msg.topic, decoded_message)
        else:
            self.message_from_other_callback(msg.topic, decoded_message)

    def on_config_received(self, config):
        # Setup all the jobs and unsubscribe any previous engagements
        self.__remove_config_job()
        room_configuration = str(config['room'])
        if room_configuration == 'removed':
            self.config_callback(False, None)
            return

        self.__setup_ping_job()
        self.room = str(config['room'])

        self.mqttclient.unsubscribe("room/#")
        self.mqttclient.unsubscribe("door/#")
        # Server or Door can ask the room to start playing or to stop
        self.mqttclient.subscribe("room/" + self.room + "/set_status", 2)
        self.mqttclient.subscribe("door/" + self.room + "/door_status", 2)
        self.mqttclient.subscribe("door/" + self.room + "/tag_scan_result", 2)

        # Do we have a special room?
        if 'roomType' in config:
            self.room_type = DoubleRoomType(str(config['roomType'])) 
            self.room_other = config['otherRoomNbr']
            self.mqttclient.subscribe("room/" + self.room_other + "/room_status", qos=2)
            print(f"ServerFinder: Recieved a double room configuration - {self.room_type.name} - other room nbr: {self.room_other}")
        else:
            self.room_type = None

        self.config_callback(True, config)

    def on_connect_event(self, clientRef, userdata, flags, rc):
        self.__remove_connect_job()
        self.mqttclient.subscribe(
            "config/" + self.macaddress + "/recieve", qos=2)
        self.connect_callback()

    def __setup_ping_job(self):
        self.__remove_ping_job()
        self.send_ping()
        # Adding seconds parameter so that not all send at the same time
        self.ping_job = self.scheduler.add_job(
            self.send_ping, 'interval', minutes=1, seconds=randint(0, 15))

    def __remove_ping_job(self):
        if self.ping_job != None:
            self.ping_job.remove()
            self.ping_job = None

    def get_room_type(self):
        return self.room_type
    
    def send_ping(self):
        ip = self.__get_ip_addr()
        message = {"mac": self.macaddress, "ip": ip, "type": "room"}
        self.mqttclient.publish("alive", json.dumps(message), qos=1)

    def __get_ip_addr(self):
        ip = "Unknown IP"
        try:
            ip = str(netifaces.ifaddresses('eth0')[2][0]['addr'])
        except KeyError:
            try:
                ip = str(netifaces.ifaddresses('wlan0')[2][0]['addr'])
                ip += " (WiFi)"
            except KeyError:
                pass
        return ip