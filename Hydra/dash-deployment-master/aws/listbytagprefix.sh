#!/bin/sh
aws ec2 --output text describe-instances --query 'Reservations[].Instances[].[InstanceId, Tags[?Key==`Name`].Value, PublicDnsName,PrivateIpAddress, State.Name]'  --filters "Name=tag:Name,Values=${1}*"
