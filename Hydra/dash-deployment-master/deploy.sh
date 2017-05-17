#!/bin/sh
####################################################
#
# Install script for CentOS 7
# TODO, make this work for OSX / Ubuntu
#
####################################################

if [ "$(id -u)" != "0" ]; then
   echo "This script must be run as root" 1>&2
   exit 1
fi

mkdir logs
mkdir aws/keys
chmod 700 aws/keys

yum install -y python-pip libffi-devel python-devel java-1.8.0-openjdk moreutils json-c sshpass

pip install --upgrade pip

pip install pyopenssl awscli softlayer pygments python-swiftclient couchdb

unzip -o -d /opt ucd/udclient.zip 
