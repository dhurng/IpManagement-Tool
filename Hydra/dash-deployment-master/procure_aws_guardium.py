#!/usr/bin/python
import json,os,sys,argparse,time,datetime,socket
from common import util
from aws import provision
from ucd import cli as ucd
from subprocess import Popen, PIPE

#########

def main(argv):
    parser = get_parser()
    args = parser.parse_args()

    global runid
    global all_instances
    elastic_ips = ''

    if args.domain is not None:
        provision.set_domain(args.domain)

    if args.ucdtoken is not None:
        ucd.set_token(args.ucdtoken)

    if args.callback is not None:
        provision.set_runid(args.callback)
        util.set_runid(args.callback)
        provision.set_awsprofile(args.awsid,args.awssecret)
        runid = args.callback
    print 'tag prefix (hostname) is ', args.tagprefix

    numnodes = 1 #int(filter(str.isdigit, args.blueprint))
    nodeconfig = 'aws/templates/guardium.json'

    tagname = '%s-guard' % args.tagprefix #"%s-node%s" % (args.tagprefix, 1 + nodeid)
    print "provisioning for tagname %s" % tagname
    instance_id = provision.create_instance(tagname, nodeconfig, args.ami, args.subnet, args.securitygroup[0])
    print "==== tagname: %s, instance_id : %s \n" % (tagname, instance_id)
    all_instances = all_instances + " " + instance_id
    order[instance_id] = {}

    nodeinfo = json.loads(provision.lookupbytag(tagname))[0]
    private_ip = nodeinfo[3]
    statereason = nodeinfo[5]
    if private_ip is None:
        print "Looks like your instances failed to come up, bummer"
        print "Clean up your resources and try again or request a limit increase on the account"
        print 'ALL_INSTANCES=', json.dumps(statereason)
        raise SystemExit()

    order[instance_id]['private_ip'] = private_ip
    order[instance_id]['hostname'] = tagname
    (stdout, stder, rc) = util.run_command("date +%s | sha256sum | base64 | head -c 24 ; echo")
    root_pw = stdout.strip()
    order[instance_id]['root_pw'] = root_pw
    order[instance_id]['nodeid'] = 1

    print "waiting for instances %s to be up \n" % all_instances
    provision.waituntilrunning(all_instances)
    # ^^ this is a lie, don't believe it
    print("Taking a nap...")
    time.sleep(120) # This is so dumb

    host_ip = provision.set_elastic_ip(instance_id, args.public)
    order[instance_id]['public_ip'] = host_ip
    elastic_ips += ' ' + host_ip

    # For testing, basically, port 22 usually wont even be open here
    if args.public:
        provision.rhel5_host_prep(host_ip, order[instance_id]['hostname'], order[instance_id]['root_pw'])
        provision.ec2('reboot-instances --instance-ids %s' % instance_id)
        # take a nap...
        time.sleep(120)
        provision.rhel5_host_prep2(host_ip, order[instance_id]['hostname'], order[instance_id]['root_pw'])
    # Otherwise, do the setup on the private side
    else:
        provision.rhel5_host_prep(order[instance_id]['private_ip'], order[instance_id]['hostname'], order[instance_id]['root_pw'])
        provision.ec2('reboot-instances --instance-ids %s' % instance_id)
        # take a nap...
        time.sleep(120)
        provision.rhel5_host_prep2(order[instance_id]['private_ip'], order[instance_id]['hostname'], order[instance_id]['root_pw'])

    ucdnodes.append({"sshid" : "root", "sshpw" : order[instance_id]['root_pw'], "role" : "guard", "ipaddress" : order[instance_id]['private_ip']})


    # report on the instances that were created by listing them by tag
    provision.describebytag(args.tagprefix)

    # print the order in json form
    print(json.dumps(order))
    capturejson['nodes'] = ucdnodes

    dumpedcapturejson = json.dumps(capturejson)
    print(dumpedcapturejson)
    if args.callback is not None:
        ucd.setapplicationprop(args.callback, dumpedcapturejson)

    print 'ALL_INSTANCES=%s' % all_instances.strip()
    print 'ELASTIC_IPS=%s' % elastic_ips.strip()
    print 'NODE_CFG=%s' % order

#########

def get_parser():
    parser = argparse.ArgumentParser(description='A helper script to provision aws ec2 instances, tag them with a suitable name and assign an elastic ip')
    parser.add_argument('-t','--tagprefix', help='a prefix used for setting the tag name of the instance (hostname)',required=True)
    parser.add_argument('-a','--ami', help='AMI ID for the dashDB base image',required=True)
    parser.add_argument('-z','--subnet', help='The VPCs subnet id where the cluster will be procured',required=True)
    parser.add_argument('-g','--securitygroup', nargs='+', help='The VPCs security group(s) associated with this cluster',required=True)
    parser.add_argument('-c','--callback', help='Application property name to put the ucd nodes information in for capture')
    parser.add_argument('-p','--public', help='Use public IP for host prep (when not running on aws dash deployment box)', action='store_true', default=False)
    parser.add_argument('-d','--domain', help='Domain to use for newly created instances')
    parser.add_argument('-u','--ucdtoken', help='UCD access token')
    parser.add_argument('-i','--awsid', help='AWS access key id')
    parser.add_argument('-s','--awssecret', help='AWS secret access key')

    return parser

#########

domain = "dashdb.cdsdev.net"
order = {}
ucdnodes = []
capturejson = {}
all_instances = ""
scriptname = sys.argv[0]
scriptdir = os.path.dirname(os.path.realpath(__file__))
runid = util.gen_id()

if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except SystemExit:
        if all_instances:
            print "Cleaning up..."
            provision.terminatebyid(all_instances)
        exit(1)

