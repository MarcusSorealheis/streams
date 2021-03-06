set -x

# Send Fusion App Data to Cloud.
curl -u $FUSION_API_CREDENTIALS -H "Content-Type:multipart/form-data" -X POST -F 'importData=@sacramento_geospatial.zip' $FUSION_API_BASE/objects/import?importPolicy=overwrite

#install core utilities
apt-get install -y build-essential libssl-dev libffi-dev python-dev python-pip libsasl2-dev libldap2-dev

# Steps:
#   Download and install Apache Superset on docker

# Docker section start ############

curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add
add-apt-repository -y "deb [arch=amd64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"
apt-get update
apt-cache policy docker-ce
apt-get install -y docker-ce
curl -L https://github.com/docker/compose/releases/download/1.24.0-rc1/docker-

docker pull tylerfowler/superset
docker run -d --name superset -p 8088:8088 tylerfowler/superset -e "MapboxAccessToken=pk.eyJ1IjoibWFyY3Vzc29yZWFsaGVpcyIsImEiOiJjanJzNXRta3EwZW9jNDRtOWtuamo5eXQwIn0.KnrylKyzKjxzcx3r5tW72Q"
# End Docker ##############

# Start Fusion Configuration changes.

# replace line in /fusion/conf/fusion.properties

sed -i "
s/group.default = zookeeper, solr, api, connectors-classic, connectors-rpc, proxy, webapps, admin-ui, sql, log-shipper/group.default = zookeeper, solr, api, connectors-classic, connectors-rpc, proxy, webapps, admin-ui, sql, log-shipper, spark-master, spark-worker/g;
" /fusion/conf/fusion.properties

#   Configure Lucidworks Fusion to work in `binary` mode in hive-site.xml.
mkdir /patch_lab
mv /fusion/conf/hive-site.xml /patch_lab
pwd
cp /superset/fusion_conf/conf/hive-site_2.xml /patch_lab
cd /patch_lab
diff -u hive-site.xml hive-site_2.xml > hive-site.patch
patch < hive-site.patch
mv hive-site.xml /fusion/conf/
# End Lucidworks configuration changes in hive-site.xml

sleep 3

/fusion/4.*/bin/fusion restart
#   Create an app in Lucidworks Fusion and index data so that you have at least one collection.

#     - TODO: include app here, that has a blob datasource done
#     - TODO: start the datasource here? done


#   Create Your First Chart
#     - TODO: can we bake this in? Don't think so, but trying.

# Diagnostics
python --version

diff -r /fusion_conf/conf/hive-site.xml /fusion/conf/hive-site.xml

diff -r /fusion_conf/conf/fusion.properties /fusion/conf/fusion.properties
