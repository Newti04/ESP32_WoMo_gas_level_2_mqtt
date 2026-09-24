import time
from machine import I2C

class BMP180:
    def __init__(self, i2c, address=0x77):
        self.i2c = i2c
        self.address = address
        # Kalibrierungsdaten vom Sensor einlesen
        self._load_calibration()

    def _load_calibration(self):
        try:
            cal = self.i2c.readfrom_mem(self.address, 0xAA, 22)
            import ustruct
            self.AC1, self.AC2, self.AC3, self.AC4, self.AC5, self.AC6, \
            self.B1, self.B2, self.MB, self.MC, self.MD = ustruct.unpack(">hhhHHHhhhhh", cal)
        except Exception as e:
            raise RuntimeError("BMP180 nicht gefunden oder I2C-Fehler:", e)

    def _read_raw_temp(self):
        self.i2c.writeto_mem(self.address, 0xF4, b'\x2E')
        time.sleep_ms(5)
        raw = self.i2c.readfrom_mem(self.address, 0xF6, 2)
        return (raw[0] << 8) + raw[1]

    def _read_raw_pressure(self):
        # OSS = 3 (Ultra-High-Resolution Modus für maximale Präzision)
        oss = 3
        self.i2c.writeto_mem(self.address, 0xF4, bytes([0x34 + (oss << 6)]))
        time.sleep_ms(26)
        raw = self.i2c.readfrom_mem(self.address, 0xF6, 3)
        return ((raw[0] << 16) + (raw[1] << 8) + raw[2]) >> (8 - oss)

    def read_values(self):
        """ Gibt (Temperatur in °C, Luftdruck in hPa) zurück """
        # Temperatur berechnen
        UT = self._read_raw_temp()
        X1 = (UT - self.AC6) * self.AC5 >> 15
        X2 = (self.MC << 11) // (X1 + self.MD)
        B5 = X1 + X2
        t = (B5 + 8) >> 4
        temperature = t / 10.0

        # Luftdruck berechnen
        UP = self._read_raw_pressure()
        oss = 3
        B6 = B5 - 4000
        X1 = (self.B2 * (B6 * B6 >> 12)) >> 11
        X2 = self.AC2 * B6 >> 11
        X3 = X1 + X2
        B3 = (((self.AC1 * 4 + X3) << oss) + 2) >> 2

        X1 = self.AC3 * B6 >> 13
        X2 = (self.B1 * (B6 * B6 >> 12)) >> 16
        X3 = ((X1 + X2) + 2) >> 2
        B4 = (self.AC4 * (X3 + 32768)) >> 15

        B7 = (UP - B3) * (50000 >> oss)
        if B7 < 0x80000000:
            p = (B7 * 2) // B4
        else:
            p = (B7 // B4) * 2

        X1 = (p >> 8) * (p >> 8)
        X1 = (X1 * 3038) >> 16
        X2 = (-7357 * p) >> 16
        pressure = p + ((X1 + X2 + 3791) >> 4)

        return temperature, round(pressure / 100.0, 2)

