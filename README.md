# MeshAdv Mini

The MeshAdv Mini is a Raspberry Pi hat designed to be used with the Linux-native version of Meshtastic known as meshtasticd. The board includes a +22dbm LoRa module, an onboard GPS module, Real Time Clock, Temperature Sensor, and breakout for I2C bus including two Qwiic connectors. 
This makes for a good "base station" or "Router" node that can be mounted high on a pole and powered over POE (using separate POE adapter or Hat). No more need to retrieve the node everytime you want to update firmware, it can all be done remotely. It also makes it easy and reliable to connect to MQTT.



Fully Assembled units available here: https://frequencylabs.etsy.com 

![](https://github.com/chrismyers2000/MeshAdv-Mini/blob/8c91e4e708419ff6cd2cfe6af8cbe80a86944f7a/Photos/3D_PCB%20MeshAdv%20Mini%20side.png)

# Info

|Pin# |GPIO|Pin Name   |Description            |   |   |Pin# |GPIO|Pin Name   |Description                      |
|-----|----|-----------|-----------------------|---|---|-----|----|-----------|---------------------------------|
|1    |    |3.3V       |                       |   |   |2    |    |5V         |                                 |
|3    |2   |SDA        |(I2C)                  |   |   |4    |    |5V         |                                 |
|5    |3   |SCL        |(I2C)                  |   |   |6    |    |GND        |                                 |
|7    |4   |GPSEN      |(GPS) GPS Enable       |   |   |8    |14  |UART TX    |(GPS)RX                          |
|9    |    |GND        |                       |   |   |10   |15  |UART RX    |(GPS)TX                          |
|11   |17  |PPS        |(GPS) 1S Pulse         |   |   |12   |18  |FANPWM     |Fan Speed PWM                    |
|13   |27  |Unused     |                       |   |   |14   |    |GND        |                                 |
|15   |22  |Unused     |                       |   |   |16   |23  |Unused     |                                 |
|17   |    |3.3V       |                       |   |   |18   |24  |RST        |(LoRa) Reset                     |
|19   |10  |MOSI       |(LoRa)                 |   |   |20   |    |GND        |                                 |
|21   |9   |MISO       |(LoRa)                 |   |   |22   |25  |Unused     |                                 |
|23   |11  |CLK        |(LoRa)                 |   |   |24   |8   |CS         |(LoRa) Chip Select               |
|25   |    |GND        |                       |   |   |26   |7   |           |                                 |
|27   |0   |Unused     |                       |   |   |28   |1   |Unused     |                                 |
|29   |5   |Unused     |                       |   |   |30   |    |GND        |                                 |
|31   |6   |Unused     |                       |   |   |32   |12  |RXEN       |(LoRa) Recieve Enable            |
|33   |13  |TXEN       |(LoRa) Transmit Enable |   |   |34   |    |GND        |                                 |
|35   |19  |Unused     |                       |   |   |36   |16  |IRQ        |(LoRa)                           |
|37   |26  |Unused     |                       |   |   |38   |20  |BUSY       |(LoRa)                           |
|39   |    |GND        |                       |   |   |40   |21  |Unused     |                                 |

== NOTICE!! always have an antenna connected to the Hat when powered on, failure to do so can damage the E22 module. ==



# Compatibility

| Raspberry Pi Model      | Working? |
|-------------------------|----------|
| Raspberry Pi 1 Model A  | No       |
| Raspberry Pi 1 Model A+ | No       |
| Raspberry Pi 1 Model B  | No       |
| Raspberry Pi 1 Model B+ | No       |
| Raspberry Pi 2 Model B  | ???      |
| Raspberry Pi 3 Model B  | ???      |
| Raspberry Pi 3 Model B+ | Yes      |
| Raspberry Pi 3 Model A+ | Yes      |
| Raspberry Pi 4 Model B  | Yes      |
| Raspberry Pi 400        | Yes      |
| Raspberry Pi 5          | Yes      |
| Raspberry Pi 500        | Yes      |
| Raspberry Pi Zero       | Yes      |
| Raspberry Pi Zero W     | Yes      |
| Raspberry Pi Zero 2 W   | Yes      |
| Raspberry Pi Pico       | Never    |
| Raspberry Pi Pico W     | Never    |





# Installing Meshtasticd

~~Watch this video first: [How to install Meshtastic on Raspberry Pi](https://www.youtube.com/watch?v=vLGoEPNT0Mk)~~ This video covers the old method, still a good video but out of date.


Official installation instructions: [https://meshtastic.org/docs/hardware/devices/linux-native-hardware/]



# Configuration


Click here for the new configuration method: [https://meshtastic.org/docs/hardware/devices/linux-native-hardware/#configuration]

The old method is below and still works if you prefer it


In /etc/meshtasticd/config.yaml, add or uncomment the following lines as needed.
```yaml
Lora:
  Module: sx1262  # Ebyte E22-900M22S choose only one module at a time
# Module: sx1268  # Ebyte E22 400M22S
  CS: 8  
  IRQ: 16
  Busy: 20
  Reset: 24
  TXen: 13
  RXen: 12
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

# Temp Sensor TMP102

The MeshAdv Mini has an onboard Texas Instruments TMP102 temp sensor soldered in the center of the board near the RTC to get a general idea of board/enclosure temperature with 0.5°C accuracy. This sensor uses I2C address 48.

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
Now, you can run the script in **three ways**:

1️⃣ **Using Python**:
   ```bash
   python3 tmp102.py
   ```

2️⃣ **Directly from CLI** (since we added a shebang and made it executable):
   ```bash
   ./tmp102.py
   ```

3️⃣ **Run in the background** (so it doesn’t stop when you close SSH):
   ```bash
   nohup ./tmp102.py &
   ```

---

## Step 7 (Optional): Auto-run at Boot
To **automatically start the script when the Raspberry Pi boots**, add it to `crontab`:

1. Open crontab:
   ```bash
   crontab -e
   ```
2. Add this line at the bottom:
   ```
   @reboot /home/pi/tmp102.py &
   ```
   *(Make sure the path to your script is correct!)*

---

## Bonus: Convert to Fahrenheit
If you also want Fahrenheit output, modify the `read_temp()` function like this:
```python
def read_temp():
    raw = bus.read_word_data(TMP102_ADDR, 0)
    raw = ((raw << 8) & 0xFF00) + (raw >> 8)
    temp_c = (raw >> 4) * 0.0625
    temp_f = temp_c * 9.0 / 5.0 + 32.0
    return temp_c, temp_f
```
And change the print statement:
```python
temp_c, temp_f = read_temp()
print(f"Temperature: {temp_c:.2f}°C | {temp_f:.2f}°F")
```

---

## ✅ You're All Set!
Now your **Raspberry Pi** reads temperature from the **TMP102 sensor** and prints it to the console! 🎉

🚀
</details>




# Real-Time Clock

The onboard Real-Time Clock (RTC) is a PCF8563 by NXP Semiconductor. This can be used to keep time in case of a power outage and GPS has not yet aquired a fix. The RTC uses I2C address 51.

<details>
  <summary>▶️ Click to Show Instructions</summary>

  ---
  
If you previously setup the Temp sensor then skip to step 3.

## Step 1: Enable I2C on Raspberry Pi
1. Open a terminal and run:
   ```sh
   sudo raspi-config
   ```
2. Navigate to **Interface Options** → **I2C** → **Enable**.
3. Reboot the Raspberry Pi:
   ```sh
   sudo reboot
   ```

## Step 2: Install I2C Tools
To verify the connection, install `i2c-tools`:
```sh
sudo apt update
sudo apt install -y i2c-tools
```



## Step 3: Load the PCF8563 Kernel Module

Check if the RTC module is detected:
```sh
i2cdetect -y 1
```
You should see an entry at **0x51** (PCF8563 default address).

Load the RTC driver manually:
```sh
sudo modprobe rtc-pcf8563
```

To make it load at boot, add it to **/boot/config.txt**:
```sh
sudo nano /boot/config.txt
```
Add the following line at the end:
```
dtoverlay=i2c-rtc,pcf8563
```
Save and exit (CTRL+X, then Y, then ENTER), then reboot:
```sh
sudo reboot
```

## Step 4: Configure the System Clock
1. Disable the fake hardware clock:
   ```sh
   sudo systemctl disable fake-hwclock
   sudo systemctl stop fake-hwclock
   ```

2. Sync the RTC with the system time:
   ```sh
   sudo hwclock --systohc
   ```

3. Enable reading from the RTC at boot:
   ```sh
   sudo hwclock -r
   ```

If the correct time is displayed, the RTC is working!

## Step 5: Synchronizing with Network Time (Optional)
To ensure the RTC stays accurate, sync with an NTP server when connected to the internet:
```sh
sudo timedatectl set-ntp on
```
Once synced, update the RTC:
```sh
sudo hwclock --systohc
```

## Step 6: Verify RTC on Reboot
Reboot the Raspberry Pi and check if the RTC retains time:
```sh
sudo hwclock -r
```
If the correct time is displayed, your RTC setup is complete! 🎉

## Troubleshooting
- If `i2cdetect -y 1` doesn't show `0x51`, check your wiring.
- Ensure `dtoverlay=i2c-rtc,pcf8563` is added correctly in `/boot/config.txt`.
- Run `dmesg | grep rtc` to check for errors.



</details>


