import math
import random
import freesans31
import _thread
from time import *
from ssd1306_setup import WIDTH, HEIGHT, setup
from writer import Writer
from rotary_irq_rp2 import RotaryIRQ
from machine import Pin, Timer, I2C, mem32
from temperature import read_scratchpad, start_temp_conversion
from rp2 import PIO, StateMachine, asm_pio

@asm_pio(out_init=(rp2.PIO.OUT_LOW,)*18, out_shiftdir=rp2.PIO.SHIFT_RIGHT)
def pwm_prog():
    pull(noblock)
    mov(x,osr)
    mov(y,isr)
    out(pins, 18)
    label("downtime")
    out(pins, null)
    jmp(y_dec, "downtime")


class PWMPINS:
    def __init__(self, sm_id, pins, pwm):
        self.pinmask = 0
        count_freq=10_000_000
        self._max_count = (1 << 16) - 1
        self._sm = StateMachine(sm_id, pwm_prog, freq=2 * count_freq, out_base=Pin(0))
        self._sm.put(pwm)
        self._sm.exec("pull()")
        self._sm.exec("mov(isr, osr)")
        self._sm.active(1)
        self._sm.put(pins)
 
    def latch(self):
        self._sm.put(self.pinmask)

    def allon(self):
        self.pinmask = 0x3FFFF
        self.latch()

    def alloff(self):
        self.pinmask = 0
        self.latch()

    def ledon(self, p):
        self.pinmask |= (1 << p)
        self.latch()

    def ledtoggle(self, p):
        self.pinmask ^= (1 << p)
        self.latch()

    def shiftleft(self):
        self.pinmask <<= 1
        self.pinmask &= 0x3FFFF
        if self.pinmask == 0:
           self.pinmask = 1
        self.latch()
    
    def shiftright(self):
        self.pinmask >>= 1
        self.pinmask &= 0x3FFFF
        if self.pinmask == 0:
           self.pinmask = 0x20000
        self.latch()
        
    def ledval(self, p):
        if p > 0:
            return (self.pinmask & (1 << p)) == True
        else:
            return -1

'''Globals'''
intensityscaler = 1
blockscreenupdate = False
mode = 2
speed = 1
temp = 0.0
freqHz = 1.0
lastthree = [None,None,None]

'''Initialize oled'''
ssd = setup(use_spi=False)
wri = Writer(ssd, freesans31)
 
'''Initialise Leds'''
leds = PWMPINS(0, 0x3FFFF, 5)


def printtoscreen(somestring, invert=False):
    wri.printstring(f'\n\n{somestring}')
    if invert:
        ssd.invert(1)
    else:
        ssd.invert(0)
    ssd.show()
    

'''Initialize Rotary encoder'''
r = RotaryIRQ(pin_num_clk=20, 
              pin_num_dt=21, 
              min_val=0, 
              max_val=17, 
              reverse=False, 
              range_mode=RotaryIRQ.RANGE_WRAP,
              pull_down=True)

encsettings = [lambda r: r.set(value=5, min_val=0, max_val=17, range_mode=RotaryIRQ.RANGE_WRAP, reverse=True),
               lambda r: r.set(value=-10, min_val=-12, max_val=12, range_mode=RotaryIRQ.RANGE_WRAP, reverse=False),
               lambda r: r.set(value=9, min_val=0, max_val=12, range_mode=RotaryIRQ.RANGE_BOUNDED, reverse=True),
               lambda r: r.set(value=9, min_val=0, max_val=12, range_mode=RotaryIRQ.RANGE_BOUNDED, reverse=True),
               lambda r: r.set(value=intensityscaler, min_val=0, max_val=30, range_mode=RotaryIRQ.RANGE_BOUNDED, reverse=True)]

modename = ["Manual", "Wheel", "Rndm 1", "Rndm 2", "Intensity"]

defaultledstate = [lambda leds: leds.alloff(),
                   lambda leds: leds.alloff(),
                   lambda leds: leds.alloff(),
                   lambda leds: leds.alloff(),
                   lambda leds: leds.allon()]

def speed_var():
    sign = lambda e: 1 if(e > 0) else -1
    if(sign(r.value()) == 1):
        leds.shiftleft()
    else:
        leds.shiftright()


def random_blink():
    leds.alloff()
    r = random.randint(0,17)
    leds.ledon(r)

     
def breathing():
    leds.alloff()
    v = r.value()
    v = (v + 1) % 18
    for x in range(v):
        rand = random.randint(0,17)
        leds.ledtoggle(rand)


'''Globals'''
modes = [None, speed_var, random_blink, breathing, None]


'''Timer/button debounce'''
def debounce(pin):
    Timer(mode=Timer.ONE_SHOT, period=500, callback=on_pressed)

def calc_temp(t):
    global temp, blockscreenupdate
    sp = read_scratchpad()
    temp = (((sp[1]<<8)+sp[0]) * 125)/2000
    if blockscreenupdate is False:
        printtoscreen(f'     {temp:>4.1f}')

def display_temperature(t):
    start_temp_conversion()
    Timer(mode=Timer.ONE_SHOT, period=100, callback=calc_temp)

def release_screen(t):
    global blockscreenupdate
    blockscreenupdate = False   

def run(timer):
    if modes[mode] is not None:
        modes[mode]()


pin_button = Pin(19, mode=Pin.IN, pull=Pin.PULL_DOWN)
pin_button.irq(trigger=Pin.IRQ_FALLING,handler=debounce)
runtim = Timer(mode=Timer.PERIODIC, freq=freqHz, callback=run)
temptim = Timer(mode=Timer.PERIODIC, period=200, callback = display_temperature)
reltim = Timer(mode=Timer.ONE_SHOT, period=2500, callback=release_screen)

def manual():
    if(mode == 0):
        lastthree[0] = lastthree[1]
        lastthree[1] = lastthree[2]
        lastthree[2] = r.value()
        if lastthree[0] is not None:
            if lastthree[0] == lastthree[2]:
                leds.ledtoggle(lastthree[1])
        leds.ledtoggle(r.value())

def onrotate():
    global speed, freqHz
    speed = r.get_max() - abs(r.value())
    freqHz = (1 + pow(speed, 4)) / 50
    runtim.deinit()
    runtim.init(mode=Timer.PERIODIC, freq=freqHz, callback=run)

def intensity():
    global intensityscaler, leds
    if(mode == 4):
        leds.allon()
        if r.value() is not intensityscaler:
            intensityscaler = r.value()
            print(intensityscaler)
            leds = PWMPINS(0, 0x3FFFF, intensityscaler*intensityscaler)

r.add_listener(onrotate)
r.add_listener(manual)
r.add_listener(intensity)

def on_pressed(t):
    global mode, modes, blockscreenupdate
    blockscreenupdate = True
    oldmode = mode
    mode = (mode + 1) % len(modes)
    printtoscreen(modename[mode], True)
    encsettings[mode](r)
    defaultledstate[mode](leds)
    reltim.deinit()
    reltim.init(mode = Timer.ONE_SHOT, period=2500, callback=release_screen)


on_pressed(None)
while True:
    continue
        
    