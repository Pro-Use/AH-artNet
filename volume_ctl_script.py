from pythonosc import udp_client
from datetime import datetime, time

QUIET_TIME_START = time(hour=5, minute=59)
QUIET_TIME_END = time(hour=22, minute=59)
client = udp_client.SimpleUDPClient("127.0.0.1", 7001)


def set_night():
    client.send_message("/1/volume1", 0.1)
    client.send_message("/1/volume2", 0.1)


def set_day():
    client.send_message("/1/volume2", 0.2)
    client.send_message("/1/volume1", 0.2)


now = datetime.now()
time_now = now.time()

if time_now > QUIET_TIME_END or time() < time_now < QUIET_TIME_START:
    set_night()
    print("setting overnight volume")
else:
    set_day()
    print("setting daytime volume")

