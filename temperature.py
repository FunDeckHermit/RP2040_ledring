from machine import Pin
import onewire, time


ow = onewire.OneWire(Pin(22)) # create a OneWire bus on GPIO22

#print(ow.scan())

 

def print_temperature(scratchpad):
    print((((scratchpad[1]<<8)+scratchpad[0]) * 125)/2000)

 

def read_scratchpad():
    ow.reset()
    ow.writebyte(0xCC)
    ow.writebyte(0xBE)
    scratchpad = [ow.readbyte() for x in range(18)]
    ow.reset()
    return scratchpad

 

def start_temp_conversion():
    ow.reset()
    ow.writebyte(0xCC)
    ow.writebyte(0x44)

 

def reset_flex_addr():
    ow.reset()
    ow.writebyte(0xCC)
    ow.writebyte(0x4E)
    ow.writebyte(0x70)
    ow.writebyte(0x00)
    ow.writebyte(0x00)
    ow.reset()

 

def start_resistor_decoding():
    ow.reset()
    ow.writebyte(0xCC)
    ow.writebyte(0x4E)
    ow.writebyte(0x70)
    ow.writebyte(0x40)
    time.sleep(0.010)
    ow.writebyte(0x55)
    ow.reset()

 

def get_gpio_status():
    ow.reset()
    ow.writebyte(0xCC)
    ow.writebyte(0xF5)
    return ow.readbyte()

 

def print_8bit_unique_id(scratchpad):
    gpio = get_gpio_status() & 0x0F
    resistor = scratchpad[6] & 0x0F
    print(hex((gpio << 4) + resistor))

   
def get_temperature():
    start_temp_conversion()
    time.sleep(1)
    scratchpad = read_scratchpad()
    return (((scratchpad[1]<<8)+scratchpad[0]) * 125)/2000

start_temp_conversion()
scratchpad = read_scratchpad()
print(print_temperature(scratchpad))
time.sleep(1)

 