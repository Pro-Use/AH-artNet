from pythonosc import udp_client


class VolCtl:
    def __init__(self):
        self.client = udp_client.SimpleUDPClient("127.0.0.1", 7001)

    def set_night(self):
        self.client.send_message("/1/volume1", 0.1)
        self.client.send_message("/1/volume2", 0.1)

    def set_day(self):
        self.client.send_message("/1/volume2", 0.2)
        self.client.send_message("/1/volume1", 0.2)