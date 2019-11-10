import vlc
import glob
import os
from threading import Event
from time import sleep


class Player:
    def __init__(self, folder):
        video_files = glob.glob(os.path.join(folder, '*.wav'))
        self.instance = vlc.Instance('--input-repeat=999999')
        self.player = self.instance.media_player_new()
        self.media = self.instance.media_new(video_files[0])
        self.player.set_media(self.media)
        self.player.play()
        print("starting audio")
        self.duration = self.player.get_length() / 1000
        self.seek_event = Event()

    def wait_on_pos(self, timecode):
        timecode *= 1000
        while self.player.get_time() < timecode:
            sleep(0.01)
        return self.player.get_time() / 1000

    def wait_on_restart(self):
        cur_pos = self.player.get_time()
        sleep(0.5)
        print("Pos: %s, waiting for restart" % (cur_pos / 1000))
        while self.player.get_time() > cur_pos:
            sleep(0.01)
        return self.player.get_time() / 1000

    def seek(self, pos):
        self.player.set_time(pos * 1000)

    def terminate(self):
        self.player.stop()
        self.instance.release()
