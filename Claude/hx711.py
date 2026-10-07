"""HX711-Treiber (Kanal A, Verstaerkung 128) mit asynchronem Mittelwert."""
from machine import Pin, disable_irq, enable_irq
import time

try:
    import uasyncio as asyncio
except ImportError:
    import asyncio


class HX711:
    def __init__(self, dout, sck):
        self.dout = Pin(dout, Pin.IN)
        self.sck = Pin(sck, Pin.OUT, value=0)

    def ready(self):
        return self.dout() == 0

    def _read(self):
        """Liest einen Rohwert. Nur aufrufen, wenn ready() True ist."""
        v = 0
        irq = disable_irq()
        for _ in range(24):
            self.sck(1)
            self.sck(0)
            v = (v << 1) | self.dout()
        # 25. Puls: naechste Messung = Kanal A, Gain 128
        self.sck(1)
        self.sck(0)
        enable_irq(irq)
        if v & 0x800000:
            v -= 1 << 24
        return v

    async def read_avg(self, n=5, timeout_ms=2000):
        """Mittelwert aus n Messungen, None bei Timeout (HX711 antwortet nicht)."""
        total = 0
        cnt = 0
        t0 = time.ticks_ms()
        while cnt < n:
            if self.dout() == 0:
                # Pruefung und Lesen ohne await dazwischen -> kein Konflikt
                total += self._read()
                cnt += 1
            else:
                if time.ticks_diff(time.ticks_ms(), t0) > timeout_ms:
                    return None
                await asyncio.sleep_ms(10)
        return total / n
