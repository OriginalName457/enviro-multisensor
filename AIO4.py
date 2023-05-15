#!/usr/bin/env python3

import time
import colorsys
import sys
import ST7735
try:
    # Transitional fix for breaking change in LTR559
    from ltr559 import LTR559
    ltr559 = LTR559()
except ImportError:
    import ltr559

from bme280 import BME280
from PIL import Image, ImageDraw, ImageFont
from fonts.ttf import RobotoMedium as UserFont
import logging

# Importing MICS6814 gas sensor
from enviroplus import gas

logging.basicConfig(
    format='%(asctime)s.%(msecs)03d %(levelname)-8s %(message)s',
    level=logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S')

logging.info("""all-in-one.py - Displays readings from all of Enviro plus' sensors

Press Ctrl+C to exit!

""")

# BME280 temperature/pressure/humidity sensor
bme280 = BME280()

# Initialize the LCD screen
disp = ST7735.ST7735(
    port=0,
    cs=1,
    dc=9,
    backlight=12,
    rotation=270,
    spi_speed_hz=10000000
)

# Initialize the font
font_size = 20
font = ImageFont.truetype(UserFont, font_size)

# Set up the canvas
image = Image.new('RGB', (disp.width, disp.height), color=(0, 0, 0))
draw = ImageDraw.Draw(image)

# The position of the top bar
top_pos = 25

# Create a list to store the sensor values
values = {
    "temperature": [1] * disp.width,
    "pressure": [1] * disp.width,
    "humidity": [1] * disp.width,
    "light": [1] * disp.width,
    "oxidised": [1] * disp.width,
    "reduced": [1] * disp.width,
    "nh3": [1] * disp.width
}

# Get the temperature of the CPU for compensation
def get_cpu_temperature():
    with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
        temp = f.read()
        temp = int(temp) / 1000.0
    return temp

# Tuning factor for compensation. Decrease this number to adjust the
# temperature down, and increase to adjust up
factor = 2.25

cpu_temps = [get_cpu_temperature()] * 5

delay = 0.5  # Debounce the proximity tap
mode = 0     # The starting mode
last_page = 0

# Display text, data, and unit on the LCD screen
def display_text(variable, data, unit):
    # Maintain length of list
    values[variable] = values[variable][1:] + [data]
    # Scale the values for the variable between 0 and 1
    vmin = min(values[variable])
    vmax = max(values[variable])
    scaled = [(v - vmin + 1) / (vmax - vmin + 1) for v in values[variable]]
    # Format the variable name and value
    message = "{}: {:.1f} {}".format(variable[:4].capitalize(), data, unit)
    logging.info(message)
    draw.rectangle((0, 0, disp.width, disp.height), (0, 0, 0))
    for i in range(disp.width):
        # Convert the color from HSV to RGB
        color = colorsys.hsv_to_rgb(i / 239.0, scaled[i], 1.0)
        # Scale the RGB values for the draw.rectangle function
        color = tuple(int(c * 255) for c in color)
        draw.rectangle((i, top_pos, i+1, disp.height), color)
    # Draw a black rectangle on top
    draw.rectangle((0, 0, disp.width, top_pos), (0, 0, 0))
    # Draw the text on top
    draw.text((0, 3), message, font=font, fill=(255, 255, 255))
    disp.display(image)

# The main loop
try:
    while True:
        proximity = ltr559.get_proximity()

        # If the proximity crosses the threshold, toggle the mode
        if proximity > 1500 and time.time() - last_page > delay:
            mode += 1
            mode %= len(values)
            last_page = time.time()

        # One mode for each variable
        if mode == 0:
            # Temperature
            unit = "C"
            cpu_temp = get_cpu_temperature()
            cpu_temps = cpu_temps[1:] + [cpu_temp]
            avg_cpu_temp = sum(cpu_temps) / float(len(cpu_temps))
            raw_temp = bme280.get_temperature()
            data = raw_temp - ((avg_cpu_temp - raw_temp) / factor)
            display_text("temperature", data, unit)

        elif mode == 1:
            # Pressure
            unit = "hPa"
            data = bme280.get_pressure()
            display_text("pressure", data, unit)

        elif mode == 2:
            # Humidity
            unit = "%"
            data = bme280.get_humidity()
            display_text("humidity", data, unit)

        elif mode == 3:
            # Light
            unit = "Lux"
            if proximity < 10:
                data = ltr559.get_lux()
            else:
                data = 1
            display_text("light", data, unit)

        elif mode == 4:
            # Oxidised
            unit = "kO"
            data = gas.read_all()
            data = data.oxidising / 1000
            display_text("oxidised", data, unit)

        elif mode == 5:
            # Reduced
            unit = "kO"
            data = gas.read_all()
            data = data.reducing / 1000
            display_text("reduced", data, unit)

            elif mode == 6:
            # NH3
            unit = "kO"
            data = gas.read_all()
            data = data.nh3 / 1000
            display_text("nh3", data, unit)

        time.sleep(0.1)  # Adjust the delay as needed

except KeyboardInterrupt:
    sys.exit(0)
