#! /usr/bin/python

import urllib2
import httplib

# Domain you want to post to: localhost would be an emoncms installation on your own laptop
# this could be changed to emoncms.org to post to emoncms.org
server = "emoncms.trenet.org"

# Location of emoncms in your server, the standard setup is to place it in a folder called emoncms
# To post to emoncms.org change this to blank: ""
emoncmspath = ""

# Write apikey of emoncms account
apikey = "..."

# Node id youd like the emontx to appear as
nodeid = 14

# Send to emoncms
# initialization HTTPConnection
conn = httplib.HTTPConnection(server)
conn.request("GET", "/"+emoncmspath+"/input/post.json?&node="+str(nodeid)+"&json="+"NT:1,VT:0"+"&apikey="+apikey)
conn.close()
