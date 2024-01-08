# HSL Clock

I came across [this tweet on X](https://twitter.com/eddible/status/1564917603180617731?s=20&t=dcHyyQINVi-xO-h7mmJiKw) and was inspired to create one for myself.

![Demo GIF](photos/demo.gif)

The project requests to Helsinki Region Transport (HSL) which uses GTFS Realtime feeds. If you are not living in Finland, I believe you can adapt this repo to other GTFS feeds with minor modifications.

If you're interested in controlling this clock with Home Assistant, I include my HA configuration here as well.

Great thanks to Edd Abrahamsen-Mills @eddible for his TFGM Metrolink Clock project <https://github.com/eddible/tfgm-tram-clock>

## Features

* Realtime public transport (metro/bus/tram) timetables.
* Realtime service alerts.
* Scroll longer station names.
* Support up to 4 destinations.
* Smooth animation.
* Support 60 fps.
* Utilize quad-core Raspberry Pi models.
* API handlings for realtime data.

## Used hardware

* [Hyperpixel 2.1 Round](https://shop.pimoroni.com/products/hyperpixel-round?variant=39381081882707)
* [Mounting Screws](https://shop.pimoroni.com/products/short-pi-standoffs-for-hyperpixel-round?variant=39384564236371) - Optional
* [Raspberry Pi Zero 2 WH](https://shop.pimoroni.com/products/raspberry-pi-zero-w?variant=39458414297171)
* Micro SD Card - Use a high endurance card, cheap ones didn't last long in my experience.
* [3D Printed Case](https://cults3d.com/en/3d-model/gadget/sphere-enclosure-w-bump-legs-m3o101-for-pimoroni-hyperpixel-2-1-round-touch-and-raspberry-pi)
* Angled micro USB cable - Optional
* USB power plug.

## Guide

### Flash your Micro SD Card

* Download [Raspberry Pi OS 32-bit Buster Lite](https://downloads.raspberrypi.org/raspios_oldstable_lite_armhf/images/raspios_oldstable_lite_armhf-2023-05-03/)
* Download the [Raspberry Pi Imager](https://www.raspberrypi.com/software/) and install it on your computer.
* Launch it with your Micro SD Card plugged into your computer.
* Click `Choose OS` → select the OS file you downloaded earlier.
* Click `Choose Storage` and select your Micro SD card.
* Click `Next` and set following configurations on the next page.
  * `Enable SSH` → `Use password authentication`.
  * `Set username and password` → Leave the username as `pi` (if you must change it, you'll need to update `transport_time.sh`) but set a password.
  * `Configure wifi` → Enter your Wi-Fi details.
  * `Save` when you're done.
* Click `Write` and wait for the OS to be written to your SD Card
* Insert it into your Pi Zero 2 W, connect it to power and give it a few minutes to complete the first boot.  

### Get your stop and route ids

* Get your stop and route ids from here <https://transitfeeds.com/p/helsinki-regional-transport/735/latest/stops>. You'll need them for configuration.
* The API endpoints in this repo are taken from here <https://hsldevcom.github.io/gtfs_rt/>

### Installing the software

* SSH into your Pi.
* Disable swap to reduce the SD card wear and also speed up system response time
  
  ```cli
  sudo dphys-swapfile swapoff
  sudo dphys-swapfile uninstall
  sudo systemctl disable dphys-swapfile
  ```

  Check whether swap is removed completely with this command `free`

* Install git:

  ```cli
  sudo apt-get update
  sudo apt install git -y
  ```

* Install the display driver then reboot:

  ```cli
  git clone https://github.com/pimoroni/hyperpixel2r
  cd hyperpixel2r
  sudo ./install.sh
  sudo reboot
  ```

* Download the code and move into the folder:  

  ```cli
  git clone https://github.com/mikenhu/hsl-clock
  cd hsl-clock
  ```

* Install required libraries:

  ```cli
  sudo apt install python3-pip -y
  sudo pip3 install -r requirements.txt
  sudo apt-get install libsdl2-mixer-2.0-0 libsdl2-image-2.0-0 libsdl2-ttf-2.0-0 -y
  ```

* You can now configure your config file with your own details. Run this command:
  * `nano config.ini`
  * Edit the file as you wish.
    * URLs: HSL APIs.
    * Language (ISO).
    * Number of timetable rows you want to have (up to 3 rows).
    * Insert your metro/bus/tram stops (from 1 up to 4 destinations). When you have more than 2 destinations, the time row is limited to 1.
      * stop_id: one stop id per entry.
      * direction_name: self-naming due to HSL data does not include the head sign names.
      * direction_id: supposedly 0 is inbound, 1 is outbound. Uneccessary at the moment.
      * route_id: can contain multiple routes per entry.
  * The content should be formatted like this:

    ```ini
    [HSL-CONFIG]
    trip_update_url = https://realtime.hsl.fi/realtime/trip-updates/v2/hsl
    service_alerts_url = https://realtime.hsl.fi/realtime/service-alerts/v2/hsl
    language = "en"
    time_row_num = 2
    stops = [
              {
                "stop_id": "1541602",
                "direction_name": "Kivenlahti",
                "direction_id": 1,
                "route_id": ["31M1"]
              }, {
                "stop_id": "1541601",
                "direction_name": "Vuosaari",
                "direction_id": 0,
                "route_id": ["31M1", "31M1B"]
              }
            ]
    ```

  * Once done, press `CTRL+X` → `Y` → `Enter`
* Next we'll set the script to launch at start up. Run these commands:

  ```cli
  sudo cp transport_startup.sh /usr/bin
  sudo chmod +x /usr/bin/transport_startup.sh
  sudo nano /etc/rc.local
  ```
  
* A text editor will open in your terminal window. Use your arrow keys to move to the bottom of the file and create a space above `exit 0` and enter this:
  
  ```bash
  bash transport_time.sh &>/dev/null
  # Disable the LED when you boot your Pi Zero 2 W to prevent light leak
  echo none | sudo tee /sys/class/leds/led0/trigger
  echo 0 | sudo tee /sys/class/leds/led0/brightness

  ```

* To save your changes, press `CTRL+X` → `Y` → `Enter`
* That's it for the software. You can run it as is. Or...

## Add Pi controls in Home Assistant

* Having the LCD always on is bad, I decided to integrate this HSL clock into my home assistant setup.

* In HA, you can execute CLI commands to control your Pi with command line and shell command integrations.

### Access your Pi from Home Assistant

* Use the `Advanced SSH & Web Terminal` community add-on on HA. Make sure **Protection mode** is off.
* Create folder to store the public key

  ```cli
  mkdir /config/.ssh
  ```

* Create a public key.

  ```cli
  ssh-keygen -t rsa
  ```

* Tell it to store it in `/config/.ssh/id_rsa`. Do not set a password for the key!
* Copy the created key to your Pi.

  ```cli
  ssh-copy-id -i /config/.ssh/id_rsa pi@[Host]
  ```

* Copy known_hosts from `/root/.ssh` to `/config/.ssh/` folder.

  ```cli
  cp /root/.ssh/known_hosts /config/.ssh/
  ```

* Try to ssh into your Pi from your HA and see if it works without a login.

  ```cli
  ssh -i /config/.ssh/id_rsa pi@[Host]
  ```

* Make sure the correct permissions are set on the `~/.ssh` directory and the `~/.ssh/authorized_keys` file on the Pi.

  ```cli
  ssh -i /config/.ssh/id_rsa pi@[Host] "chmod 700 ~/.ssh && chmod 600 ~/.ssh/authorized_keys"
  ```

### Create the switches and buttons in Home Assistant

Copy my config below into your `configuration.yaml` file and make it match your network setup.

* Command line

```yaml
command_line:
  - switch:
      name: Transport Dashboard Screen
      unique_id: transport_dashboard_screen
      command_off: 'ssh -o HostKeyAlgorithms=+ssh-rsa -o PubkeyAcceptedKeyTypes=+ssh-rsa -o UserKnownHostsFile=/config/.ssh/known_hosts -i /config/.ssh/id_rsa -q pi@[Host] "sudo -E sh -c ''echo 1 > /sys/class/backlight/rpi_backlight/bl_power''"'
      command_on: 'ssh -o HostKeyAlgorithms=+ssh-rsa -o PubkeyAcceptedKeyTypes=+ssh-rsa -o UserKnownHostsFile=/config/.ssh/known_hosts -i /config/.ssh/id_rsa -q pi@[Host] "sudo -E sh -c ''echo 0 > /sys/class/backlight/rpi_backlight/bl_power''"'
      command_state: 'ssh -o HostKeyAlgorithms=+ssh-rsa -o PubkeyAcceptedKeyTypes=+ssh-rsa -o UserKnownHostsFile=/config/.ssh/known_hosts -i /config/.ssh/id_rsa -q pi@[Host] "cat /sys/class/backlight/rpi_backlight/bl_power"'
      value_template: '{{ value == "0" }}'
```

* Shell command

```yaml
shell_command:
  restart_pi: 'ssh -o HostKeyAlgorithms=+ssh-rsa -o PubkeyAcceptedKeyTypes=+ssh-rsa -o UserKnownHostsFile=/config/.ssh/known_hosts -i /config/.ssh/id_rsa -q pi@[Host] "sudo reboot"'
  shutdown_pi: 'ssh -o HostKeyAlgorithms=+ssh-rsa -o PubkeyAcceptedKeyTypes=+ssh-rsa -o UserKnownHostsFile=/config/.ssh/known_hosts -i /config/.ssh/id_rsa -q pi@[Host] "sudo shutdown -h now"'
```
