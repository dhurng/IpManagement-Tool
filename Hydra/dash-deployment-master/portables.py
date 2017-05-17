#!/usr/bin/python
import argparse,sys,json,os,SoftLayer,couchdb
from SoftLayer import NetworkManager
from SoftLayer import utils
from common import util
from softlayer import sl
from softlayer.IPChecker import IPChecker
from ucd import cli
from multiprocessing.dummy import Pool as ThreadPool

#########

DEBUG = False
PCNI = False
environment = ''
zonesdb = None
portablesdb = None

def main(argv):
    parser = get_parser()
    args = parser.parse_args()
    if args.debug:
        print 'DEBUG output is ON'
    util.DEBUG = args.debug
    global DEBUG
    global environment

    environment = args.environment
    DEBUG = args.debug
    sl.DEBUG = args.debug
    sl.set_creds(args.slid, args.slkey)
    args.func(args)

def initialize_couch_connection(args):
    global zonesdb
    global portablesdb

    couch = couchdb.Server(args.repo)
    creds = args.repocreds.split(':')
    couch.resource.credentials = (creds[0], creds[1])
    zonesdb = couch['deploymentzones']
    portablesdb = couch['portableips']

def get_parser():
    parser = argparse.ArgumentParser(description='Main entry point for manipulating SoftLayer portable IPs')
    parser.add_argument('environment', help='The deployment environment which owns the portable IPs')
    parser.add_argument('slid', help='Softlayer id')
    parser.add_argument('slkey', help='Softlayer api key')
    parser.add_argument('repo', help='The cloudant repository where information about portable IP usage is tracked')
    parser.add_argument('repocreds', help='The API credentials for the cloudant repository where portable IP usage is tracked')
    parser.add_argument('-d', '--debug', default=False, action='store_true', help='Turns on additional debug logging')

    subparsers = parser.add_subparsers(title='subcommands', description='valid subcommands', help='additional help')

    parser_scan = subparsers.add_parser('scan', help='scan for dashDB portable IPs')
    parser_scan.add_argument('--vlanonly', default=False, action='store_true', help='will only scan the current VLAN as opposed to a full scan which will do the entire account')
    parser_scan.set_defaults(func=scan)

    parser_assign = subparsers.add_parser('assign', help='assign a portable IP to a target environment')
    parser_assign.add_argument('target', help='The target UCD environment where this portable IP will be used')
    parser_assign.set_defaults(func=assign)

    parser_release = subparsers.add_parser('release', help='release a portable IP to be reusable')
    parser_release.add_argument('portable', help='the portable IP to release back to the pool')
    parser_release.set_defaults(func=release)

    parser_add = subparsers.add_parser('add', help='add a new portable subnet managed by dashDB')
    parser_add.add_argument('--subnet', help='The new subnet to add under management by dashDB', required=True)
    parser_add.add_argument('--vlanonly', default=True,help='will only scan the current VLAN as opposed to a full scan which will do the entire account')
    parser_add.set_defaults(func=addportable)

    parser_report = subparsers.add_parser('report', help='generates a report of managed portable IP usage only')
    parser_report.set_defaults(func=genreport)

    return parser

def scan(args):
    initialize_couch_connection(args)
    details = getenvinfo(args)
    zones = []
    results = []
    if not args.vlanonly:
        for zone in details['zones']:
            if zone['location'] == 'softlayer':
                ips = getmanagedips(zone['publicVLANid'])
                if len(ips) == 0:
                    continue
                zones.append((zone, ips))
    else:
        ips = getmanagedips(details['relay']['publicVLANid'])
        global PCNI
        if details['props']['PCNI'] == 'true':
            PCNI = True
        zones.append((details['relay'], ips))

    poolsize = len(zones)
    pool = ThreadPool(poolsize)
    # scan each zone in its own thread and return the results
    results = pool.map(scan_zone, zones)
    #close the pool and wait for the work to finish 
    pool.close()
    pool.join()

    report(args, results)

def genreport(args):
    details = getenvinfo(args)
    zones = []
    results = []
    for zone in details['zones']:
        if zone['location'] == 'softlayer':
            zones.append(zone)

    for zone in zones:
        ips = getmanagedips(zone['publicVLANid'])
        if len(ips) == 0:  # We're done here
            continue
        results.append((zone, ips))

    report(args, results)

def report(args, results):
    for (zone, result) in results:
        vlanid = zone['publicVLANid']
        vlan_details = sl.get_vlan_details(vlanid)
        dc = vlan_details['primaryRouter']['datacenter']['name']
        vlanname = '%s: %s' % (vlan_details['vlanNumber'], vlan_details['name'] if 'name' in vlan_details.keys() else 'Unnamed')
        zonename = zone['name']
        formathdr = '{:=^19}{:=^62}{:=^10}{:=^13}{:=^33}{:=^43}'
        formatstr = '| {:<16} | {:<59} | {:^7} | {:<10} | {:<29} | {:<40} |'
        print ''
        print formathdr.format('Portable IP', 'Status', 'DC', 'VLAN ID', 'VLAN Name', 'UCD Relay Zone')
        for ip in result:
            ipAddress = ip['ipAddress']
            status = ip['note'] if ip.has_key('note') else 'Unknown'
            print formatstr.format(ipAddress, status, dc, vlanid, vlanname, zonename)

def scan_zone((zone, ips)):
    if len(ips) == 0:  # We're done here
        return None

    ipstocheck = []
    for ip in ips: # find the ones in the cloudant db and normalize new entries for updates
        address = ip['ipAddress']
        if address in portablesdb:
            portable = portablesdb[address]
            ip['reserved'] = portable['reserved']
            ip['available'] = portable['available']
            if not portable['reserved']:  # Don't check the reserved ones
                ipstocheck.append(ip)
            else:
                ip['available'] = False
        else:
            ip['reserved'] = False
            ip['available'] = False
            ipstocheck.append(ip)

    # Add this zone to the cloudant repo if it doesn't already exist
    if str(zone['publicVLANid']) not in zonesdb:
        zone['publicVLAN'] = sl.get_vlan_details(zone['publicVLANid'])
        zone['privateVLAN'] = sl.get_vlan_details(zone['privateVLANid'])
        zonesdb[str(zone['publicVLANid'])] = zone

    with IPChecker(zone) as ipcheck:
        ipcheck.DEBUG = DEBUG
        if PCNI:
            if DEBUG:
                print 'Using PCNI settings (local SVL check only)'
            ipcheck.IPCheckProcess = 'Toolserver: Check Portable IP Firewall Rules From SVL'
        for ip in ips:
            if not ipcheck.checkifipinuse(ip) and ip in ipstocheck:
                ipcheck.checkfirewallrules(environment, ip)
        ipcheck.updateresults(portablesdb, zone['publicVLANid'])
        return (zone, ipcheck.results.values())

def assign(args):
    HAPatterns = ['production.hadr.8.500GB.template.txn', 'production.hadr.128.1.6TB.txn']
    guardiumPatterns = ['guardium', 'guardium-aws']
    details = getenvinfo(args)
    vlanid = details['relay']['publicVLANid']
    portable = None

    # First check to see if the environment already has a portable
    targetprops = cli.get_env_props(args.target)
    propnames = [x['name'] for x in targetprops]
    if 'portableIP' in propnames:
        portableIP = [x['value'] for x in targetprops if x['name'] == 'portableIP'][0]
        print 'PortableIP=%s' % portableIP
        raise SystemExit(0) # Exit clean, we're done here.

    pattern = cli.get_env_prop(args.target, 'sl-pp')
    # Dev/Test systems normally don't get a portable IP
    if details['props']['env.type'] == 'Dev' or details['props']['env.type'] == 'Test':
        # handle HA systems like prod 
        if pattern not in HAPatterns:
            print 'PortableIP=localhost'
            portable = 'localhost'

    # Make sure we're not deploying a Guardium system
    if pattern in guardiumPatterns:
        print 'PortableIP=localhost'
        portable = 'localhost'

    # If we still don't have a portable yet
    if portable is None:
        ## Don't initialize portables DB TILL HERE!!
        initialize_couch_connection(args)
        avail_vr = portablesdb.view('by_zone/available')
        available = avail_vr[str(vlanid)].rows
        # And if there is any available in this vlan
        if len(available) > 0:
            # Grab the first available one
            ip = portablesdb[available[0]['id']]
            ip['reserved'] = True
            ip['available'] = False
            # Mark it as reserved and unavailalbe prior to updating properties in UCD
            portablesdb[ip['_id']] = ip
            portable = ip['_id']
            # Update the SL notes for good measure
            sl.update_note_on_ip(ip['SoftlayerID'], args.target)
            print 'Assigning IP'
            print 'ZoneName=%s' % details['relay']['name']
            print 'PortableIP: %s' % ip['ipAddress']
            print 'REMAINING: %s' % (len(available) - 1)

    # If we got this far and assigned something we should update UCD
    if portable is not None:
        cli.setenvprop(args.target, 'portableIP', portable)
    # Or we just failed and we should error out and quit
    elif details['props']['env.type'] == 'Dev' or details['props']['env.type'] == 'Test':
        print 'PortableIP=localhost'
        portable = 'localhost'
        cli.setenvprop(args.target, 'portableIP', portable)
    else:
        print 'Unable to find a free portable IP!!!'
        raise SystemExit(1) # Production systems should fail

def getmanagedips(vlanid):
    subnets = sl.get_dash_portable_subnets(vlanid)
    print 'Found %s portable subnets in vlan ID# %s' % (len(subnets), vlanid)
    managed = []
    for subnet in subnets:
        ips = sl.get_ips_in_subnet(subnet['id'])
        for ip in ips:
            if not ip['isReserved'] and not ip['isBroadcast'] and not ip['isNetwork'] and not ip['isGateway']:
                managed.append(ip)
    if len(managed) > 0:
        details = sl.get_vlan_details(vlanid)
        print 'Found %s dashDB managed portable IPs in VLAN ID# %s (non-unique number: %s and colloquially referred to as "%s") not marked as reserved by softlayer, gateway ips, network ips or broadcast ips' % (len(managed), vlanid, details['vlanNumber'], details['name'])
    return managed

def release(args):
    initialize_couch_connection(args)
    ip = portablesdb[args.portable]
    ip['reserved'] = False
    ip['available'] = True
    portablesdb[ip['_id']] = ip
    sl.update_note_on_ip(ip['SoftlayerID'], 'Available')
    print 'Released %s back to the pool of avaialable portable IPs' % args.portable

def addportable(args):
    details = getenvinfo(args)

    # Validate the subnet details
    subnetdetails = sl.get_subnet_details(args.subnet)
    vlanid = details['relay']['publicVLANid']
    vlan_details = sl.get_vlan_details(vlanid)
    vlanname = '%s: %s' % (vlan_details['vlanNumber'], vlan_details['name'] if 'name' in vlan_details.keys() else 'Unnamed')
    if int(subnetdetails['networkVlanId']) != int(details['relay']['publicVLANid']):
        print 'ERROR: Subnet %s does not seem to belong to VLAN %s - %s which is the current target for % - %s.  Please retry from a more appropriate deployment environment.' % (args.subnet, vlanid, vlanname, args.environment, details['relay']['name'])
        raise SystemExit
    if subnetdetails['subnetType'] != 'SECONDARY_ON_VLAN':
        print 'ERROR: This is not a portable subnet!'
        raise SystemExit
    sl.update_note_on_subnet(args.subnet)
    scan(args)

def getenvinfo(args):
    result = {}
    props = cli.get_component_env_props('dynamite-controller', args.environment)
    result['props'] = props
    zones = cli.get_relay_zones()
    result['zones'] = zones['zones']
    for zone in zones['zones']:
        if zone['name'] == props['RestrictedVLAN']:
            result['relay'] = zone
    return result

if __name__ == '__main__':
   main(sys.argv[1:])
