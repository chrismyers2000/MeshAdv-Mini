![](https://github.com/chrismyers2000/MeshAdv-Mini/blob/298581bdf106296083a373f97896de44633c6cd1/Data/Misc/MeshAdv%20Mini%20Logo.png)

---


==The MeshAdv Mini has just been released, the project and this README is currently a work in progress==

The MeshAdv Mini is a Lora/GPS Raspberry Pi hat designed to be used with the Linux-native version of [Meshtastic](https://meshtastic.org/) known as [meshtasticd](https://meshtastic.org/docs/hardware/devices/linux-native-hardware/). It is similar to its big brother, the [MeshAdv Pi Hat](https://github.com/chrismyers2000/MeshAdv-Pi-Hat), but half the size and fits perfectly on the Pi Zero lineup. The board includes a +22dbm LoRa module, integrated GPS module, HAT+ EEPROM, Temperature Sensor, 5V PWM Fan header, and breakout for I2C bus including two Qwiic connectors. 
This makes for a good "base station" or "Router" node that can be mounted high on a pole and powered over POE (using separate POE adapter or Hat). No more need to retrieve the node everytime you want to update firmware, it can all be done remotely. It also makes it easy and reliable to connect to MQTT.

---

Fully Assembled units available here: https://frequencylabs.etsy.com


![](https://github.com/chrismyers2000/MeshAdv-Mini/blob/6fad3e7618cef262edfb8fcbe4b52011aaec8268/Photos/Top_3D_PCB%20MeshAdv%20Mini%20Stackable.png)

== NOTICE!! always have an antenna connected to the LoRa module when powered on, failure to do so can damage the module. ==

# Info

|Pin# |GPIO|Pin Name   |Description            |   |   |Pin# |GPIO|Pin Name   |Description                      |
|-----|----|-----------|-----------------------|---|---|-----|----|-----------|---------------------------------|
|1    |    |3.3V       |                       |   |   |2    |    |5V         |                                 |
|3    |2   |SDA        |(I2C1)                 |   |   |4    |    |5V         |                                 |
|5    |3   |SCL        |(I2C1)                 |   |   |6    |    |GND        |                                 |
|7    |4   |GPSEN      |(GPS) GPS Enable       |   |   |8    |14  |UART TX    |(GPS)RX                          |
|9    |    |GND        |                       |   |   |10   |15  |UART RX    |(GPS)TX                          |
|11   |17  |PPS        |(GPS) 1 Sec Pulse      |   |   |12   |18  |FANPWM     |Fan Speed PWM                    |
|13   |27  |Unused     |                       |   |   |14   |    |GND        |                                 |
|15   |22  |Unused     |                       |   |   |16   |23  |Unused     |                                 |
|17   |    |3.3V       |                       |   |   |18   |24  |RST        |(LoRa) Reset                     |
|19   |10  |MOSI       |(LoRa)                 |   |   |20   |    |GND        |                                 |
|21   |9   |MISO       |(LoRa)                 |   |   |22   |25  |Unused     |                                 |
|23   |11  |CLK        |(LoRa)                 |   |   |24   |8   |CS         |(LoRa) Chip Select               |
|25   |    |GND        |                       |   |   |26   |7   |           |                                 |
|27   |0   |ID-SDA     |(I2C0) For HAT+ EEPROM |   |   |28   |1   |ID-SCL     |(I2C0) For HAT+ EEPROM           |
|29   |5   |Unused     |                       |   |   |30   |    |GND        |                                 |
|31   |6   |Unused     |                       |   |   |32   |12  |RXEN       |(LoRa) Recieve Enable            |
|33   |13  |Unused     |                       |   |   |34   |    |GND        |                                 |
|35   |19  |Unused     |                       |   |   |36   |16  |IRQ        |(LoRa)                           |
|37   |26  |Unused     |                       |   |   |38   |20  |BUSY       |(LoRa)                           |
|39   |    |GND        |                       |   |   |40   |21  |Unused     |                                 |





# Compatibility

| Raspberry Pi Model      | Working? |
|-------------------------|----------|
| Raspberry Pi 1 Model A  | Never*   |
| Raspberry Pi 1 Model A+ | ???      |
| Raspberry Pi 1 Model B  | Never*   |
| Raspberry Pi 1 Model B+ | ???      |
| Raspberry Pi 2 Model B  | Yes      |
| Raspberry Pi 3 Model B  | Yes      |
| Raspberry Pi 3 Model B+ | Yes      |
| Raspberry Pi 3 Model A+ | Yes      |
| Raspberry Pi 4 Model B  | Yes      |
| Raspberry Pi 400        | Yes      |
| Raspberry Pi 5          | Yes      |
| Raspberry Pi 500        | Yes      |
| Raspberry Pi Zero       | Yes      |
| Raspberry Pi Zero W     | Yes      |
| Raspberry Pi Zero 2 W   | Yes      |
| Raspberry Pi Pico       | Never*   |
| Raspberry Pi Pico W     | Never*   |

*Raspberry Pi `1 Model A`, `1 Model B`, and `Pico` do not implement the 40-pin layout used in the MeshAdv Pi Hat.



# Installing Meshtasticd

~~Watch this video first: [How to install Meshtastic on Raspberry Pi](https://www.youtube.com/watch?v=vLGoEPNT0Mk)~~ This video covers the old method, still a good video but out of date.


Official installation instructions: [https://meshtastic.org/docs/hardware/devices/linux-native-hardware/]



# Configuration

==This hat features HAT+ compatibility with an onboard EEPROM for quick setup. This feature is currently experimental==

These instructions assume you are using a raspberry pi with Raspberry Pi OS. 

## New Method:

   - As methods keep changing, please [CLICK HERE](https://meshtastic.org/docs/hardware/devices/linux-native-hardware/?os=raspbian) for the most up to date configuration process
   - There was an error in the initial config.d file. It has been fixed but may take a while to migrate to Beta. Please copy the file from here in the meantime: [Download](https://github.com/chrismyers2000/MeshAdv-Mini/blob/4c952fa066cf92b278a3ad54c8098b99bcde8b93/Data/lora-MeshAdv-Mini-900M22S.yaml)
---
## Old Method:

   - The old method is below and still works if you prefer it


```bash
sudo nano /etc/meshtasticd/config.yaml
```
add or uncomment the following lines as needed.

```yaml
Lora:
  Module: sx1262  # Ebyte E22-900M22S choose only one module at a time
# Module: sx1268  # Ebyte E22 400M22S
  CS: 8  
  IRQ: 16
  Busy: 20
  Reset: 24
  RXen: 12
  DIO2_AS_RF_SWITCH: true
  DIO3_TCXO_VOLTAGE: true

GPS:
  SerialPath: /dev/ttyS0

I2C:
  I2CDevice: /dev/i2c-1

Logging:
  LogLevel: info # debug, info, warn, error

Webserver:
  Port: 443 # Port for Webserver & Webservices
  RootPath: /usr/share/meshtasticd/web # Root Dir of WebServer

General:
  MaxNodes: 200
```
## LoRa Setup:

- You must now set the LoRa Region to be able to start using Meshtastic. [CLICK HERE](https://meshtastic.org/docs/getting-started/initial-config/#set-regional-settings) for info on how to set region settings. Please note: Linux-Native is currently unable to connect over bluetooth or to the Apple app. All other methods are working. 

---

# GPS
   
   - The ATGM336H-5NR32 can receive the GPS and BeiDou constellations. It is fully integrated into the MeshAdv Mini with the ability to put the GPS to sleep for low power consumption and also utilize the PPS output for very precise time keeping, useful for running an NTP server alongside Meshtastic.
   - Backup Battery: The recommended GPS backup battery is the official [Raspberry Pi 5 RTC battery](https://www.raspberrypi.com/products/rtc-battery/). This is a rechargable battery so make sure you do not use a standard non-rechargable battery.
   - Start by following the official instructions to get the GPS working with meshtasticd [CLICK HERE](https://meshtastic.org/docs/hardware/devices/linux-native-hardware/#uart-raspberry-pi)
   - GPS can be turned on or off manually using GPIO4. If you do not plan to use this feature and you want to enable it full-time, you need to change the startup setting for the GPIO pin.

        Edit the `config.txt` file:
        ```bash
        sudo nano /boot/firmware/config.txt
        ```

        Add the following line to the bottom
        ```bash
        gpio=4=op,dh #Enables GPS
        ```
         
   - ### PPS Time Correction:
      <details>
      <summary>▶️ Click to Show Instructions</summary>
            
   
      ## 1. Enable PPS Support in Raspberry Pi OS
      Edit the `config.txt` file:
      
      ```bash
      sudo nano /boot/firmware/config.txt
      ```
      
      Add the following line at the bottom:
      ```bash
      dtoverlay=pps-gpio,gpiopin=17
      ```
      
      Save and exit (`CTRL+X`, then `Y`, then `ENTER`).
      
      Reboot the Raspberry Pi:
      ```bash
      sudo reboot
      ```
      
      ---
      
      ## 2. Verify PPS Signal
      After reboot, check if the **PPS device is detected**:
      ```bash
      ls /dev/pps*
      ```
      Expected output:
      ```bash
      /dev/pps0
      ```
      Install `pps-tools`:
      ```bash
      sudo apt update
      sudo apt install pps-tools
      ```
      
      Check if PPS is generating pulses:
      ```bash
      sudo ppstest /dev/pps0
      ```
      Expected output (timestamps every second):
      ```
      trying PPS source "/dev/pps0"
      found PPS source "/dev/pps0"
      ok, found 1 source(s), now start fetching data...
      source 0 - assert 1672531199.999999999, sequence: 12345 - clear  0.000000000, sequence: 0
      ```
      
      ---
      
      ## 3. Sync System Time with PPS
      Install `chrony`:
      ```bash
      sudo apt update
      sudo apt install chrony
      ```
      
      Edit the **Chrony config**:
      ```bash
      sudo nano /etc/chrony/chrony.conf
      ```
      
      Add the following at the end:
      ```bash
      # Use PPS signal for accurate timing
      refclock PPS /dev/pps0 lock GPS prefer
      ```
      
      Restart Chrony:
      ```bash
      sudo systemctl restart chronyd
      ```
      
      Check PPS synchronization:
      ```bash
      chronyc sources -v
      ```
      Expected output should show PPS as a preferred time source.
      
      ---
   
      ## 4. (Optional) Sync GPS Time via NMEA
      If you want **both GPS time and PPS**, modify `chrony.conf` to include:
      ```bash
      refclock SHM 0 delay 0.5 refid GPS
      refclock PPS /dev/pps0 lock GPS prefer
      ```
      </details>
   
---  
   
# Temp Sensor TMP102

   - The MeshAdv Mini has an onboard Texas Instruments TMP102 temp sensor soldered in the center of the board near the EEPROM to get a general idea of board/enclosure temperature with 0.5°C accuracy. This sensor uses I2C address 48.

<details>
  <summary>▶️ Click to Show Instructions</summary>


---


## Step 1: Enable I2C on the Raspberry Pi
1. Open the Raspberry Pi configuration tool:
   ```bash
   sudo raspi-config
   ```
2. Go to **"Interface Options" > "I2C"**, enable it, and exit.
3. Reboot the Pi to apply changes:
   ```bash
   sudo reboot
   ```

---

## Step 2: Install Required Packages
Update your package list and install **I2C tools** and **Python SMBus**:
```bash
sudo apt update
sudo apt install i2c-tools python3-smbus -y
```

---

## Step 3: Verify the TMP102 Connection
Find the **I2C address** of the TMP102 sensor:
```bash
sudo i2cdetect -y 1
```
- If connected correctly, you should see **0x48** (default address).

---

## Step 4: Create the Python Script
1. Open a new script file:
   ```bash
   sudo nano tmp102.py
   ```

2. Paste the following Python code:
   ```python
   #!/usr/bin/env python3
   import smbus
   import time

   # I2C setup
   bus = smbus.SMBus(1)  # Use I2C bus 1
   TMP102_ADDR = 0x48  # Default I2C address for TMP102

   def read_temp():
       """Reads temperature from TMP102 and converts it to Celsius"""
       raw = bus.read_word_data(TMP102_ADDR, 0)
       
       # Swap byte order (TMP102 stores in little-endian)
       raw = ((raw << 8) & 0xFF00) + (raw >> 8)
       
       # Convert to temperature (TMP102 uses 12-bit resolution)
       temp_c = (raw >> 4) * 0.0625
       return temp_c

   if __name__ == "__main__":
       while True:
           print(f"Temperature: {read_temp():.2f}°C")
           time.sleep(1)
   ```

3. Save and exit (`CTRL+X`, then `Y`, then `Enter`).

---

## Step 5: Make the Script Executable
Run this command to **make the script executable**:
```bash
sudo chmod +x tmp102.py
```

---

## Step 6: Run the Script
Now, you can run the script in **two ways**:

1️⃣ **Using Python**:
   ```bash
   python3 tmp102.py
   ```

2️⃣ **Directly from CLI**:
   ```bash
   ./tmp102.py
   ```


---

</details>


---

# PWM Fan

   - The onboard PWM fan connector can support 2 wire 5V fans (Always on), and 4-pin PWM (Tach not implemented). I recommend the [Noctua NF-A4x10 5V PWM 40mm](https://a.co/d/4vufchq) 0r [Noctua NF-A8 5V PWM 80mm](https://a.co/d/56CNeq1)

   - Setup:   
      <details>
        <summary>▶️ Click to Show Instructions</summary>
      
        ---
      
      
      ## Option 1: (Easiest - Works with Pi 4 and 5 only) Use the built-in fan control tool to turn fan on and off
      
      1. Open the `raspi-config` tool by running the following:
         ```bash
         sudo raspi-config
         ```
      2. Navigate to the "Performance Options" section.
      3. Select "Fan" and enable the fan control.
      4. Set the GPIO pin to 18 and temperature threshold for the fan to start. By default, the fan starts at 60°C, but you can modify this by editing the `/boot/firmware/config.txt` file manually.
         ```bash
         sudo nano /boot/firmware/config.txt
         ```
         add the following:
         ```bash
         dtoverlay=gpio-fan,gpiopin=18,temp=60000
         ```
      6. Exit and reboot
      
         ---
      
      ## Option 2 (works for most Pi models)
      
      1. Install the `Rpi.GPIO` Python library
         ```bash
         sudo apt update && sudo apt install python3-rpi.gpio
         ```
      2. Create a new file called `fan_control.py`
         ```bash
         sudo nano fan_control.py
         ```
      3. Copy the following and save the file:
         ```bash
         #!/usr/bin/env python3
         import RPi.GPIO as GPIO
         import time
      
         # Configuration
         FAN_PIN = 18
         TEMP_THRESHOLD_LOW = 45.0  # Temperature (°C) at which fan runs at minimum speed
         TEMP_THRESHOLD_HIGH = 60.0  # Temperature (°C) at which fan runs at max speed
      
         # Initialize GPIO
         GPIO.setmode(GPIO.BCM)
         GPIO.setup(FAN_PIN, GPIO.OUT)
         pwm = GPIO.PWM(FAN_PIN, 25000)  # 25 kHz PWM frequency
         pwm.start(0)  # Start with fan off
      
         def get_cpu_temp():
             """Reads the CPU temperature."""
             with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                 return int(f.read()) / 1000  # Convert from millidegrees to degrees
      
         def set_fan_speed(temp):
             """Adjusts fan speed based on temperature."""
             if temp < TEMP_THRESHOLD_LOW:
                 duty_cycle = 0  # Fan off
             elif temp > TEMP_THRESHOLD_HIGH:
                 duty_cycle = 100  # Full speed
             else:
                 # Scale between min and max speed
                 duty_cycle = (temp - TEMP_THRESHOLD_LOW) / (TEMP_THRESHOLD_HIGH - TEMP_THRESHOLD_LOW) * 100
             pwm.ChangeDutyCycle(duty_cycle)
      
         try:
             while True:
                 temp = get_cpu_temp()
                 set_fan_speed(temp)
                 print(f"CPU Temp: {temp:.1f}°C | Fan Speed: {int(pwm.ChangeDutyCycle)}%")
                 time.sleep(5)  # Check every 5 seconds
         except KeyboardInterrupt:
             print("Fan control stopped")
             pwm.stop()
             GPIO.cleanup()
         ```
      4. Make the file executable
         ```bash
         chmod +x fan_control.py
         ```
      5. Optional: Run script at boot
         ```bash
         crontab -e
         ```
         Add this line at the end:
         ```bash
         @reboot /usr/bin/python3 /path/to/fan_control.py &
         ```
         Hint: use pwd command to find your current directory. Change "/path/to" the location of your script.
      
      
      
      </details>
      
      |Pin|Name    |Color |
      |---|--------|------|
      |1  |Ground  |Black |
      |2  |5V      |Yellow|
      |3  |NC      |Green |
      |4  |PWM     |Blue  |

