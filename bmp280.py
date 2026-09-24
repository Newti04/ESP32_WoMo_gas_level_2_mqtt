import time
import ustruct

class BMP280:
    def __init__(self, i2c, address=0x76):
        self.i2c = i2c
        self.address = address
        
        # Sensor konfigurieren (Normal Mode, Oversampling x1)
        try:
            self.i2c.writeto_mem(self.address, 0xF4, b'\x27')
            self.i2c.writeto_mem(self.address, 0xF5, b'\x00')
        except Exception as e:
            raise RuntimeError("BMP280 nicht unter der I2C-Adresse gefunden:", e)
            
        self._load_calibration()

    def _load_calibration(self):
        cal = self.i2c.readfrom_mem(self.address, 0x88, 24)
        self.dig_T1, self.dig_T2, self.dig_T3, \
        self.dig_P1, self.dig_P2, self.dig_P3, self.dig_P4, self.dig_P5, \
        self.dig_P6, self.dig_P7, self.dig_P8, self.dig_P9 = ustruct.unpack("<HhhHhhhhhhhh", cal)

    def read_values(self):
        """ Gibt (Temperatur in °C, Luftdruck in hPa) zurück """
        try:
            # Alle 6 Datenregister auf einmal auslesen
            data = self.i2c.readfrom_mem(self.address, 0xF7, 6)
            
            # Präzises Bit-Parsing der Rohdaten
            raw_press = (data[0] << 12) | (data[1] << 4) | (data[2] >> 4)
            raw_temp = (data[3] << 12) | (data[4] << 4) | (data[5] >> 4)

            # 1. Temperatur-Kompensation (Offizielle Bosch-Formel)
            var1 = (((raw_temp >> 3) - (self.dig_T1 << 1)) * self.dig_T2) >> 11
            var2 = (((((raw_temp >> 4) - self.dig_T1) * ((raw_temp >> 4) - self.dig_T1)) >> 12) * self.dig_T3) >> 14
            t_fine = var1 + var2
            temperature = ((t_fine * 5 + 128) >> 8) / 100.0

            # 2. Luftdruck-Kompensation (Offizielle Bosch-Formel)
            var1 = (t_fine) - 128000
            var2 = var1 * var1 * self.dig_P6
            var2 = var2 + ((var1 * self.dig_P5) << 17)
            var2 = var2 + (self.dig_P4 << 35)
            var1 = ((var1 * var1 * self.dig_P3) >> 8) + ((var1 * self.dig_P2) << 12)
            var1 = (((1 << 63) + var1) * self.dig_P1) >> 33

            if var1 == 0:
                pressure = 0.0
            else:
                p = 1048576 - raw_press
                p = int((((p << 31) - var2) * 3125) / var1)
                var1 = (self.dig_P9 * (p >> 13) * (p >> 13)) >> 25
                var2 = (self.dig_P8 * p) >> 19
                pressure = ((p + var1 + var2) >> 8) + (self.dig_P7 << 4)
                pressure = (pressure / 256.0) / 100.0

            return round(temperature, 1), round(pressure, 1)
        except Exception:
            return 0.0, 0.0

