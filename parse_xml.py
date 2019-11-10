
import xml.etree.ElementTree as ET
import datetime

tree = ET.parse('xml_from_vezer_10nov.xml')
root = tree.getroot()
keyframes = root[0][0][0][4]
start = 0.0

for keyframe in keyframes:
    seconds = float(keyframe[0].text) / 30
    fade_time = seconds - start
    timecode = datetime.timedelta(seconds=seconds)
    h, m, s = str(timecode).split(":")
    timecode = "%s:%s" % (m, s)
    print("['%s', light_ctl.fade, {'universe': 'master', 'fade_to': %s, 'fade_time': %s}]," %
          (timecode, keyframe[1].text, fade_time))
    start = seconds
