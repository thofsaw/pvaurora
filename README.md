# pvaurora

 Aurora power inverter uploader to pvoutput.org
 
 ## Description
 
 pvaurora is a python package that interacts with the 
 [curtronics aurora tool](http://www.curtronics.com/Solar/AuroraData.html) to provide photo-voltaic system power 
 generation data to [pvoutput.org](https://pvoutput.org). The curtronics aurora tool grabs a snapshot of the power generation 
 details directly from the aurora inverter. The tool can gather data from more than one string on multiple 
 inverters. 
 
 Currently, the pvaurora python package supports only one inverter and assumes two strings. It provides two data points 
 to pvoutput.org:
  * Cumulative Daily Energy Output (= Energy Generated on pvoutput.org); and
  * Instantaneous Total Power Output (= Power Generated on pvoutput.org).
  
  The second data point is the sum of the instantaneous power from string 1 and string 2.
 
 ## Installation Notes
 
 Follow these manual steps:
 1. Download the package (zip or git clone) to your chosen local directory
 1. Create a virtualenv directory `python3 -m venv venv`
 1. Activate your virtualenv `source <path-to-venv-dir>/venv/bin/activate`
 1. Install the dependencies
    ```
    pip3 install requests click
    ```
 1. Install the curtronics aurora tool `apt install aurora`
 1. Confirm that you get some command line options help when you run `python3 <path-to-pvaurora>/src/pvaurora.py --help`
 
 ## Running
 
pvaurora needs some configuration parameters to run successfully. Copy `config.json` from 
`<path-to-pvaurora>/doc` to another convenient location, e.g. `<path-to-pvaurora>`. Edit the contents of the file in a 
text editor as follows:
```
{
  "command": The aurora tool command with full path. You'll need in include the parameters I've used in this example 
    for the script to work: 
    "/usr/local/bin/aurora -a2 -c -d0 -e -P 400 -Y 20 /dev/ttyUSB0",
  "api_key": The key from pvoutput.org. You can get this key from the account settings page (https://pvoutput.org/account.jsp)
    "<api-key-from-pvoutput.org>",
  "system_id": The system id of your registered output system. You can also get this from the account settings page:
    12345,
  "minutes_delta": This is the amount of minutes added to your local time if your region has daylight savings: 
    60,
  "latitude": Latitude of your solar installation. Only used to calculate sunrise and sunset times: 
    12.34,
  "longitude": Longitude of your solar installation. Only used to calculate sunrise and sunset times:
    123.34
}
```

Run pvaurora with the configuration and confirm success:
```
python3 <path-to-pvaurora>/src/pvaurora.py -v --config <path-to-config.json-file/config.json
```
You should see output similar to below (stripped of some details):
```
INFO:root:Parameter command = /usr/local/bin/aurora -a2 -c -d0 -e -P 400 -Y 20 /dev/ttyUSB0
INFO:root:Parameter api_key = ....
INFO:root:Parameter system_id = ....
INFO:root:Parameter minutes_delta = 60
INFO:root:Parameter latitude = ....
INFO:root:Parameter longitude = ....
INFO:root:Date   : YYYY-MM-DD
INFO:root:Time   : hh:mm:ss.ssssss
INFO:root:Sunrise: hh:mm:ss
INFO:root:Sunset : hh:mm:ss
INFO:root:Delta  : 1:00:00
INFO:root:Daylight time
INFO:root:Executing '/usr/local/bin/aurora -a2 -c -d0 -e -P 400 -Y 20 /dev/ttyUSB0'
INFO:root:Return code = 0
INFO:root:Output 'b'   296.853729       2.845379     844.661499     311.433472       5.791459    1803.654053     234.191910      10.472196    2437.221436      49.983006      92.029121      60.095478      55.414928       23.456       23.456        0.000      844.658      844.658    68945.075    68945.075    OK\n''
INFO:root:b'   296.853729       2.845379     844.661499     311.433472       5.791459    1803.654053     234.191910      10.472196    2437.221436      49.983006      92.029121      60.095478      55.414928       23.456       23.456        0.000      844.658      844.658    68945.075    68945.075    OK\n'
INFO:root:Sending: {'d': 'YYYYMMDD', 't': 'HH:MM', 'v1': 23456.0, 'v2': 2648.315552}
INFO:root:https://pvoutput.org/service/r2/addstatus.jsp?....
INFO:root:POST ok: 200 OK
INFO:root:Completed successfully
```
 
 
