"""Minimaler BMP280-Treiber (I2C), Integer-Kompensation nach Bosch-Datenblatt."""
import ustruct
import time


class BMP280:
    def __init__(self, i2c, addr=None):
        self.i2c = i2c
        if addr is None:
            found = i2c.scan()
            if 0x76 in found:
                addr = 0x76
            elif 0x77 in found:
                addr = 0x77
            else:
                raise OSError("BMP280 nicht gefunden")
        self.addr = addr
        chip = i2c.readfrom_mem(addr, 0xD0, 1)[0]
        if chip not in (0x56, 0x57, 0x58, 0x60):
            raise OSError("Unbekannte Chip-ID %x" % chip)
        calib = i2c.readfrom_mem(addr, 0x88, 24)
        self.c = ustruct.unpack("<HhhHhhhhhhhh", calib)
        # osrs_t x2, osrs_p x16, normal mode
        i2c.writeto_mem(addr, 0xF4, b"\x57")
        # Standby 500 ms, IIR-Filter 4
        i2c.writeto_mem(addr, 0xF5, b"\x88")
        time.sleep_ms(100)

    def read(self):
        """Gibt (Temperatur in Grad C, Druck in hPa) zurueck."""
        d = self.i2c.readfrom_mem(self.addr, 0xF7, 6)
        adc_p = (d[0] << 12) | (d[1] << 4) | (d[2] >> 4)
        adc_t = (d[3] << 12) | (d[4] << 4) | (d[5] >> 4)
        T1, T2, T3, P1, P2, P3, P4, P5, P6, P7, P8, P9 = self.c

        v1 = (((adc_t >> 3) - (T1 << 1)) * T2) >> 11
        v2 = (((((adc_t >> 4) - T1) * ((adc_t >> 4) - T1)) >> 12) * T3) >> 14
        t_fine = v1 + v2
        temp = ((t_fine * 5 + 128) >> 8) / 100

        v1 = t_fine - 128000
        v2 = v1 * v1 * P6
        v2 = v2 + ((v1 * P5) << 17)
        v2 = v2 + (P4 << 35)
        v1 = ((v1 * v1 * P3) >> 8) + ((v1 * P2) << 12)
        v1 = (((1 << 47) + v1) * P1) >> 33
        if v1 == 0:
            return temp, None
        p = 1048576 - adc_p
        p = (((p << 31) - v2) * 3125) // v1
        v1 = (P9 * (p >> 13) * (p >> 13)) >> 25
        v2 = (P8 * p) >> 19
        p = ((p + v1 + v2) >> 8) + (P7 << 4)
        return temp, p / 25600.0
