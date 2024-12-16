import os
import gc
import time
import ujson
import machine
import network
import esp
import esp32

from ssl import SSLContext
from ssl import PROTOCOL_TLS_CLIENT

esp.osdebug(True, esp.LOG_DEBUG)

print("Loading values from NVS:")
nvs = esp32.NVS("certs")
#thing_name = "000004"
buffer = bytearray(2048)
nvs.get_nvsstr("thingname",buffer)
thing_name = str(buffer.decode().strip('\x00'))
print("ThingName " + thing_name)

nvs.get_nvsstr("certificate", buffer)
cert = bytes(buffer.decode().strip('\x00'), 'utf-8')
#print("Cert: " + cert)

nvs.get_nvsstr("priv_key", buffer)
key = bytes(buffer.decode().strip('\x00'), 'utf-8')
#print("Key: " + key)


configTopic = "/" + thing_name + "/config"

theDisplay = None  #this will be set later as an object defined by a class in a dynamically loaded python file
client = None   #will become the MQTT client object

options = []
subscriptions = []
resubscribeRequired = True

# private_key = "private.key"
# private_cert = "cert.pem"

#to convert to binary key and cert, use these commands
#openssl x509 -outform der -in cert.pem  -out cert.der
#openssl rsa -inform pem -in private.key -outform der -out key.der

#cert and key must be in der form
# with open('key.der','rb') as f:
#     KEY=f.read()
# with open('cert.der', 'rb') as f:
#     CERT=f.read()

#We need a robust MQTT client that handles disonnects and unreliable wifi
#clone this repo somewhere else, and then symlink the mqtt_as folder into the modules folder
#https://github.com/peterhinch/micropython-mqtt/tree/master
from mqtt_as import MQTTClient
import uasyncio as asyncio
from mqtt_as import config



async def subscribeToAll(client, subscriptions):
    global resubscribeRequired
    print("Subscribing to all topics.")
    for s in subscriptions:
        print("Subscribing to " + s)
        await client.subscribe(s,1)
    resubscribeRequired = False

# Subscription callback
def sub_cb(topic, msg, retained):
    global subscriptions, options, resubscribeRequired, theDisplay
    #print(f'Topic: "{topic.decode()}" Message: "{msg.decode()}" Retained: {retained}')
    message = ujson.loads(msg)
    #print(topic, message)
    #the topic comes back as a byte array
    if(topic.decode('utf-8') == configTopic):
        if message['options']:
            options = message['options']
            #print(message['options'])
        if message['subscriptions']:
            subscriptions = message['subscriptions']
            #print(message['subscriptions'])   
            resubscribeRequired = True                    
        if message['configuration']:
            # #put the configuration contents into a temporary python file
            # f = open("LumiqDisplay.py", "w")
            # f.write(message['configuration'])
            # f.close()
            # tmp_module = __import__("LumiqDisplay")
            # LumiqDisplay = getattr(tmp_module, "LumiqDisplay")
            # theDisplay = LumiqDisplay(options = options)                    

            #this is a fun workaround to load a module dynamically without creating a file first
            module_dict = {}
            # Execute the code within the module's __dict__
            exec(message['configuration'], module_dict)
            LumiqDisplay = module_dict["LumiqDisplay"]
            theDisplay = LumiqDisplay(options = options)
            
    else:                
        print("Data received.")
        theDisplay.ingestData(message)

async def wifi_han(state):
    print('Wifi is ', 'up' if state else 'down')
    await asyncio.sleep(1)

# If you connect with clean_session True, must re-subscribe (MQTT spec 3.1.2.4)
async def conn_han(client):    
    if theDisplay == None:
        print("Subscribing to " + configTopic)
        await client.subscribe(configTopic,1)
    resubscribeRequired = True


async def main(client):
    global subscriptions, resubscribeRequired
    await client.connect()
    while True:
        #print(resubscribeRequired, subscriptions)
        gc.collect()
        if resubscribeRequired:
            await subscribeToAll(client, subscriptions)
        await asyncio.sleep(10)  # Broker is slow        

# Define configuration
config['server'] = 'aqhafcthj4nmx-ats.iot.us-east-2.amazonaws.com'  
config['subs_cb'] = sub_cb
config['connect_coro'] = conn_han
config['wifi_coro'] = wifi_han
config['ssl'] = True
config['ssl_params'] = {'do_handshake':False, 'key':key, 'cert':cert} 
# Not needed if you're only using ESP8266
config['ssid'] = 'CritterNet'
config['wifi_pw'] = 'CharlieCat'
config['client_id'] = thing_name
# Set do_handshake to false to defer the SSL handshake, somehow makes ssl connection works

# Set up client
MQTTClient.DEBUG = True  # Optional
client = MQTTClient(config)

loop = asyncio.get_event_loop()
#loop.create_task(heartbeat())
try:
    loop.run_until_complete(main(client))
finally:
    client.close()  # Prevent LmacRxBlk:1 errors
