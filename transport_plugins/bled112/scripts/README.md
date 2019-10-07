##Scripts to check gateway throughput

_profile_gateway.py_ creates two virtual terminals, instatiate the gateway, hardware manager, bled112 mock and profiles performance of the gateway
```bash
python profile_gateway.py --time-to-profile 10 --log-file log.txt --max-advertisements-per-second 100 --unique-devices 20 --stream-value-update-probability 50 --connect-ws
```

##Steps
First a virtual serial port should be created:
```bash
$ socat -d -d pty,raw,echo=0 pty,raw,echo=0

2019/07/30 15:36:40 socat[31169] N PTY is **/dev/pts/5**
2019/07/30 15:36:40 socat[31169] N PTY is **/dev/pts/8**
2019/07/30 15:36:40 socat[31169] N starting data transfer loop with FDs [10,10] and [12,12]
```

We need the two sides of serial connection **/dev/pts/5** and **/dev/pts/8** in my case.

Now we can launch a script that will mock bled112 dongle, it will try to push
**1000** adv packets every second to the gateway, the bunch will contains 20 unique
macs and streaming value will change with probability 5%.

```bash
python run_mock_observer.py --max-advertisements-per-second **1000** --port /dev/pts/5 \
    --unique-devices 20 --stream-value-update-probability 5
```

Also we need to run gateway, there is a script that profiles gateway as it works
and save log data to supplied file, --time-to-profile specifies how long gateway should work,
connect-ws specifies if an connection to HardwareManager via websocket should be established
```bash
python run_gateway.py --time-to-profile 200 --port /dev/pts/8 --log-file log1.txt --connect-ws
```
