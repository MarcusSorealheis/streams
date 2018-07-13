#!/bin/bash

# ... Galvanize
#         (To arouse to awareness or action)

# hostname convention: button-<stream id>-<instance id>
SID=`hostname | cut -d '-' -f 2` # stream ID (aka app name)
IID=`hostname | cut -d '-' -f 3` # instance ID

echo "SID: $SID"
echo "IID: $IID"

sudo su -

# First some Java...
add-apt-repository ppa:webupd8team/java -y
echo debconf shared/accepted-oracle-license-v1-1 select true | sudo debconf-set-selections
echo debconf shared/accepted-oracle-license-v1-1 seen true | sudo debconf-set-selections


apt-get update -y
apt-get install oracle-java8-installer -y
apt install oracle-java8-set-default -y
echo JAVA_HOME="/usr/lib/jvm/java-8-oracle" >> /etc/environment

# `jq` is in the "main universe"
echo "deb http://us.archive.ubuntu.com/ubuntu vivid main universe" >> /etc/apt/sources.list
apt-get install jq -y
apt-get install unzip -y

# Look up details for stream $SID, say "lou"
# curl https://streams.lucidworks.com/api/stream/lou
# {'id': 'y4xt',
# 'fusion_version': '7.4',
# 'repo': 'https://github.com/lucidworks/streams/projects/sockitter/dev',
# etc....
# }

# Fake a stream/app definition for now...
STREAM_JSON='{"sid": "lou", "fusion_version":"4.0.2", "distro": "lou-buttons.tgz", "admin_password": "password123"}'

DISTRO=`echo $STREAM_JSON | jq -r .distro`
ADMIN_PASSWORD=`echo $STREAM_JSON | jq -r .admin_password`

##
#    stream/app-specific handling
##
mkdir $SID

gsutil cp gs://buttons-streams/$DISTRO $SID/

cd $SID
tar xvfz $DISTRO
./buttons-start.sh

#
# apt-get install maven -y
# apt-get install ant -y

IP=$(wget -qO- http://ipecho.net/plain)

cd /; git clone https://github.com/lucidworks/streams

# only download and untar if we do not have a /fusion directory
if [ ! -d "/fusion" ]; then
# #############################
# # if fusion not installed
# #############################

wget -nv https://storage.cloud.google.com/buttons-streams/fusion-4.0.2.tar.gz
tar xvfz fusion-4.0.2.tar.gz

# link up fusion
ln -s /fusion/ /root/fusion

# replace line in /fusion/conf/fusion.properties
sed -i "
s,solr.jvmOptions = -Xmx2g -Xss256k,solr.jvmOptions = -Xmx2g -Xss256k -Denable.runtime.lib=true,g;
" /fusion/conf/fusion.properties

# restart
/fusion/4.0.2/bin/fusion restart

# set the password
curl -X POST -H 'Content-type: application/json' -d '{"password":"$ADMIN_PASSWORD"}' http://localhost:8764/api

# #############################
# # end if fusion not installed
# #############################
# else
/fusion/bin/fusion restart
fi

echo "$SID has been Galvanized"
