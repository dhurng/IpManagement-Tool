#!/usr/bin/python
import json,os,sys,argparse
from softlayer import sl
from ucd import cli
from SoftLayer import utils
from common import util

DEBUG = False

def main(argv):
    parser = get_parser()
    args = parser.parse_args()
    global DEBUG

    if args.debug:
        print 'DEBUG output is ON'
        util.DEBUG = args.debug
        sl.DEBUG = args.debug
        cli.DEBUG = args.debug
        DEBUG = args.debug

    if args.slid is not None:
        sl.set_creds(args.slid,args.slapi)

    set_environment_properties(args)

    # Now run the fix dedicated process
    cli.setenvprop(args.name, 'bluemix.dedicated', 'true')
    # Rerun Initial Setup (should fix the dedicated stuff)
    cli.submit_and_wait('Initial Setup', args.name)
    # FIN

def set_environment_properties(args):
    # Find the TEMRelay
    hosts = sl.get_systems_by_base_hostname('*TEMRelay')
    hosts = hosts.values()
    if len(hosts) < 1:
        print 'Unable to find TEMRelay!'
        raise SystemExit(1)
    temrelay = hosts[0] # Because I've never seen more than one (even though we could in theory have HA
    cli.setenvprop(args.name, 'dedicated.iem.hostname', temrelay['fullyQualifiedDomainName'])
    cli.setenvprop(args.name, 'dedicated.iem', temrelay['primaryBackendIpAddress'])

    # Find the QRadar IP.. this one is a bit more complicated
    hosts = sl.get_systems_by_base_hostname('qradar')
    hosts = hosts.values()
    if len(hosts) < 1:
        print 'Unable to find any QRadar Hosts!'
        raise SystemExit(1)
    if len(hosts) == 1: # Very unlikely
        cli.setenvprop(args.name, 'dedicated.qradar', hosts[0]['primaryBackendIpAddress'])
    else:
        qradarhost = hosts[0] # pickone
        if qradarhost['vm']:
            details = sl.mgr.get_instance(qradarhost['id'])
        else:
            details = sl.bm.get_hardware(qradarhost['id'])
        vlans = details['networkVlans']
        # Find the private VLAN ID for the qradar host
        if vlans[0]['networkSpace'] == 'PRIVATE':
            qradar_vlan = vlans[0]['id']
        else:
            qradar_vlan = vlans[1]['id']

        # Find the portable subnets for this private vlan
        filter = utils.NestedDict({})
        filter['subnets']['subnetType']['operation'] = "SECONDARY_ON_VLAN" #This isn't working
        filter['subnets']['networkVlanId']['operation'] = qradar_vlan
        subnets = sl.net.list_subnets(filter=filter.to_dict())

        for subnet in subnets:
            if subnet['subnetType'] == 'SECONDARY_ON_VLAN':
                # Now check the Subnet
                if DEBUG:
                    print 'Found possible QRadar subnet, %s.. checking..' % subnet['id']
                ips = sl.get_ips_in_subnet(subnet['id'])
                for ip in ips:
                    if not ip['isReserved'] and not ip['isBroadcast'] and not ip['isNetwork'] and not ip['isGateway']:
                        if ip.has_key('note') and 'qradar' in ip['note'].lower():
                            # We found one so lets try it
                            if DEBUG:
                                print 'Checking possible QRadar IP, %s, with note: %s...' % (ip['ipAddress'], ip['note'])
                            if check_qradar_ip(ip['ipAddress']):
                                cli.setenvprop(args.name, 'dedicated.qradar', ip['ipAddress'])
                                return # If this returns true, we're done

        # If we exhausted all subnets and didn't find a working QRadar IP we need to error out
        print 'I was unable to find a working QRadar IP'
        raise SystemExit(1)

def check_qradar_ip(address):
    try:
        util.run_command('nmap -p 514 %s | grep 514 | awk \'{print $2}\' | grep open' % address)
        return True
    except SystemExit:
        return False

def get_parser():
    parser = argparse.ArgumentParser(description='Bootstrap a Bluemix Dedicated Softlayer environment and push the appropriate properties to the UCD deployment environment for furture deployments.')
    parser.add_argument('name', help='Name of the deployment environment (dedicated environment where we are running from right now)')
    parser.add_argument('-i','--slid', help='Softlayer id')
    parser.add_argument('-k','--slapi', help='Softlayer API key')
    parser.add_argument('-d','--debug', help='Turn debug logging on', default=False, action='store_true')

    return parser

if __name__ == "__main__":

    main(sys.argv[1:])
