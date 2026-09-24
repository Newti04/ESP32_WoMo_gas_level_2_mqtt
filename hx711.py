import time
from machine import Pin

class HX711:
    def __init__(self, d_out, pd_sck, gain=128):
        self.pOUT = Pin(d_out, Pin.IN)
        self.pSCK = Pin(pd_sck, Pin.OUT, value=0)
        self.GAIN = 0
        self.OFFSET = 0
        self.SCALE = 1
        self.set_gain(gain)

    def set_gain(self, gain):
        if gain == 128: self.GAIN = 1
        elif gain == 64: self.GAIN = 3
        elif gain == 32: self.GAIN = 2

    def is_ready(self):
        return self.pOUT.value() == 0

    def read(self):
        while not self.is_ready():
            time.sleep_us(10)

        raw = 0
        # 24-Bit Daten auslesen
        for _ in range(24):
            self.pSCK.value(1)
            raw = (raw << 1) | self.pOUT.value()
            self.pSCK.value(0)

        # Gain-Puls(e) senden
        for _ in range(self.GAIN):
            self.pSCK.value(1)
            self.pSCK.value(0)

        # 2er-Komplement für negative Werte auflösen
        if raw & 0x800000:
            raw -= 0x1000000

        return raw

    def read_average(self, times=10):
        summe = 0
        for _ in range(times):
            summe += self.read()
        return summe / times

    def tare(self, times=15):
        summe = self.read_average(times)
        self.OFFSET = summe

    def set_scale(self, scale):
        self.SCALE = scale

    def get_units(self, times=5):
        return (self.read_average(times) - self.OFFSET) / self.SCALE

