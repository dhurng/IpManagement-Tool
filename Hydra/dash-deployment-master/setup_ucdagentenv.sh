#!/bin/sh
proxyhost=`grep 'agent.http.proxy.host' /opt/ibm-ucd/agent/conf/agent/installed.properties | awk -F "=" '{print $2}'`
proxyport=`grep 'agent.http.proxy.port' /opt/ibm-ucd/agent/conf/agent/installed.properties | awk -F "=" '{print $2}'`
DS_WEB_URL=https://ucdeploy.swg-devops.com
https_proxy=\"http://$proxyhost:$proxyport\"

dedicated=$1

i=0
if [ ! -z $proxyhost ] && [ ! -z $proxyport ]; then
  if [ $(grep -c "proxyHost=$proxyhost" /etc/ucdagent.env) -ne 1 ];then
    i=$((i+1));
  fi
  if [ $(grep -c "proxyPort=$proxyport" /etc/ucdagent.env) -ne 1 ];then
    i=$((i+1));
  fi
  if [ $(grep -c "HTTPS_PROXY=$https_proxy" /etc/ucdagent.env) -ne 1 ];then
    echo "HTTPS_PROXY is NOT set, but maybe this is a dedicated environment"
  fi
fi
if [ $(grep -c "DS_WEB_URL=https://ucdeploy.swg-devops.com" /etc/ucdagent.env) -ne 1 ];then
  i=$((i+1));
fi
echo $i errors in the ucdagent.env
if [ $i -gt 0 ] && [ "${dedicated}" == "true" ]; then
  cat << EOFD > /etc/ucdagent.env
DS_WEB_URL=$DS_WEB_URL
proxyHost=$proxyhost
proxyPort=$proxyport
EOFD
  echo FIRSTRUN=true
elif [ $i -gt 0 ]; then
  cat << EOF > /etc/ucdagent.env
DS_WEB_URL=$DS_WEB_URL
proxyHost=$proxyhost
proxyPort=$proxyport
HTTPS_PROXY=$https_proxy
EOF
  echo FIRSTRUN=true
else
  echo FIRSTRUN=false
fi
