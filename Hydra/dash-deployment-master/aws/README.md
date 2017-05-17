provision.py is the main script. It uses a profile json to procure EC2 instances & associate an elastic ip with each instance. 

./provision.py -h
usage: provision.py [-h] -t TAGPREFIX -p PROFILE [-n NUMNODES]

A helper script to provision aws ec2 instances, tag them with a suitable name
and assign an elastic ip

optional arguments:
  -h, --help            show this help message and exit
  -t TAGPREFIX, --tagprefix TAGPREFIX
                        a prefix used for setting the tag name of the instance
  -p PROFILE, --profile PROFILE
                        Profile json file name
  -n NUMNODES, --numnodes NUMNODES
                        number of nodes


(-n 3 would create 3 nodes of that "profile" type)

Example run:
./provision.py -p ./devtest.json  -t dash-loaddev1 -n 3

this creates 3 nodes with "devtest.json" profile - and the EC2 instances will all have the dash-loaddev1-node1, -node2, -node3  names associated with it.

Example profiles:

micro.json - simple t2.micro deployed with ami-d2c924b2 (centos 7 in us-west-2) in a particular us-west-2 vpc/subnet with the dashdb security group. Useful for quick testing of the script itself & other aspects

devtest.json - similar to micro - except that it has the 10 EBS volumes needed for an MPP node & deploys a r3.8xlarge EC2 instance

devtest.us-east-1.json - similar to devtest.json - but has references to the us-east-1 ami for centos 7 & a vpc/subnet/security group created in that region.
