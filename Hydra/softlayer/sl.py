#!/usr/bin/python
# -*- coding: utf-8 -*-
"""A collection of helper functions for interacting with the SL
python API and making dashDB deployment scripting easier.
"""
import json,os,sys,shutil
import SoftLayer,time,itertools
from SoftLayer import utils
from SoftLayer.exceptions import SoftLayerAPIError
from common import util

client = SoftLayer.create_client_from_env()
mgr = SoftLayer.VSManager(client)
bm = SoftLayer.HardwareManager(client)
net = SoftLayer.NetworkManager(client)
dns = SoftLayer.DNSManager(client)

HARDWARE = 'Hardware_Server'
"""The string to feed `reload_server` for a hardware reload
"""

VIRTUAL = 'Virtual_Guest'
"""The string to feed `reload_server` for a virtual server reload
"""

ZONE_ID_LON=1740168
"""The zone_id for services.eu-gb.bluemix.net
"""

ZONE_ID_DAL=1665181
"""The zone_id for services.dal.bluemix.net
"""

ZONE_ID_SYD=1831180
"""The zone_id for services.au-syd.bluemix.net
"""

SWIFT_DC_MAPPING = {
    'amsterdam'         : 'ams01',
    'frankfurt'         : 'fra02',
    'melbourne'         : 'mel01',
    'seoul'             : 'seo01',
    'sydney'            : 'syd01',
    'washington'        : 'wdc',      # LOL
    'chennai'           : 'che01',
    'hongkong'          : 'hkg02',
    'mexico'            : 'mex01',
    'paris'             : 'par01',
    'sanjose'           : 'sjc01',
    'tokyo'             : 'tok02',
    'dallas'            : 'dal05',
    'london'            : 'lon02',
    'milan'             : 'mil01',
    'saopaulo'          : 'sao01',
    'singapore'         : 'sng01',
    'toronto'           : 'tor01',
    'houston'           : 'dal05',
    'oslo'              : 'fra02',
    'seattle'           : 'sjc01'
}
"""Mapping the closest datacenter to a city for swift object storage
"""

SL_TO_BLUEMIX_MAPPING = {
        'amsterdam'         : 'United_Kingdom',
        'frankfurt'         : 'United_Kingdom',
        'melbourne'         : 'Sydney',
        'seoul'             : 'Sydney',
        'sydney'            : 'Sydney',
        'washington'        : 'US_South',
        'chennai'           : 'Sydney',
        'hongkong'          : 'Sydney',
        'mexico'            : 'US_South',
        'paris'             : 'United_Kingdom',
        'sanjose'           : 'US_South',
        'tokyo'             : 'Sydney',
        'dallas'            : 'US_South',
        'london'            : 'United_Kingdom',
        'milan'             : 'United_Kingdom',
        'saopaulo'          : 'US_South',
        'singapore'         : 'Sydney',
        'toronto'           : 'US_South',
        'houston'           : 'US_South',
        'oslo'              : 'United_Kingdom',
        'seattle'           : 'US_South'
}
"""Mapping of closest bluemix region to a softlayer city
"""

PUBLIC_SERVICES_DOMAINS = {
    'United_Kingdom'    : 'services.eu-gb.bluemix.net',
    'US_South'          : 'services.dal.bluemix.net',
    'Sydney'            : 'services.au-syd.bluemix.net'
}
"""Mapping of bluemix regions to domain names that dashDB uses for those domains.
"""

BACKUP_TIME_MAPPING = {
'houston' : '8',
'mexico' : '8',
'washington' : '7',
'sanjose' : '10',
'milan' : '1',
'london' : '2',
'amsterdam' : '1',
'seattle' : '10',
'dallas' : '8',
'paris' : '1',
'hongkong' : '18',
'sydney' : '15',
'chennai' : '20',
'seoul' : '17',
'singapore' : '18',
'toronto' : '7',
'tokyo' : '17',
'melbourne' : '15',
'saopaulo' : '4',
'oslo' : '1',
'frankfurt' : '1',
'montreal' : '7'
}

dnsrecords={}

DEBUG=False

###########
@util.run_once
def set_creds(username, apikey):
    """Sets the SoftLayer API credentials and recreates the client.

    Args:
        username (str): softlayer user name
        apikey (str): api key associated with the user

    """
    global client
    global mgr
    global net
    global dns
    global bm
    for x in range(5):
        client = SoftLayer.create_client_from_env(username=username, api_key=apikey)
        try:
            client.call('Account', 'getObject')
            break
        except Exception:
            print 'Oops, unable to get account object when setting credentials, maybe we\'re in US-Fed?'
            client = SoftLayer.create_client_from_env(username=username, api_key=apikey, endpoint_url='https://api.service.usgov.softlayer.com/xmlrpc/v3.1/')
            try:
                client.call('Account', 'getObject')
                break
            except Exception:
                print 'Both failed... maybe there is a general network failure happening... waiting a few before trying again...'
                time.sleep(5)
    else:
        print 'Tried 5 times to connect to SoftLayer using the supplied credentials (both the regular and US-Fed endpoints) and I\'m giving up at this point...'
        raise SystemExit(1)
    mgr = SoftLayer.VSManager(client)
    net = SoftLayer.NetworkManager(client)
    dns = SoftLayer.DNSManager(client)
    bm = SoftLayer.HardwareManager(client)

###########

def find_host(name):
    """Finds a host by hostname.

    Args:
        name (str): name of the host to find

    Returns:
        json: Some details about the host

    """
    host = mgr.list_instances(hostname=name)

###########

def get_dash_portable_subnets(vlan):
    """Finds all portable subnets in a given VLAN that are marked as suitable for Hydra use.
    Expects portable subnets that are for dash use to have 'dashDB Portable Subnet' in their notes field
    and will ignore any that do not have that exactly.

    Args:
        vlan (int): the vlan id to search for portable subnets

    Returns:
        json: a list of portable subnets for dashDB use.

    """
    filter = utils.NestedDict({})
    filter['subnets']['note']['operation'] = "dashDB Portable Subnet"
    filter['subnets']['subnetType']['operation'] = "SECONDARY_ON_VLAN"
    filter['subnets']['networkVlanId']['operation'] = vlan
    return net.list_subnets(filter=filter.to_dict())

###########

def get_hydra_portable_subnets(vlan):
    """Finds all portable subnets in a given VLAN that are marked as suitable for Hydra use.
    Expects portable subnets that are for dash use to have 'Hydra Portable Subnet' in their notes field
    and will ignore any that do not have that exactly.

    Args:
        vlan (int): the vlan id to search for portable subnets

    Returns:
        json: a list of portable subnets for dashDB use.

    """
    filter = utils.NestedDict({})
    filter['subnets']['note']['operation'] = "Hydra Portable Subnet"
    filter['subnets']['subnetType']['operation'] = "SECONDARY_ON_VLAN"
    filter['subnets']['networkVlanId']['operation'] = vlan
    return net.list_subnets(filter=filter.to_dict())

###########

def get_all_dash_portable_subnets():
    """Finds all portable subnets in the current account that are marked as suitable for dashDB use.
    Expects portable subnets that are for dash use to have 'dashDB Portable Subnet' in their notes field
    and will ignore any that do not have that exactly.

    Returns:
        json: a list of portable subnets for dashDB use.

    """
    filter = utils.NestedDict({})
    filter['subnets']['note']['operation'] = "dashDB Portable Subnet"
    filter['subnets']['subnetType']['operation'] = "SECONDARY_ON_VLAN"
    return net.list_subnets(filter=filter.to_dict())

###########

def update_note_on_ip(ip_id, note):
    """Updates the notes field of an IP address in Softlayer.

    Args:
        ip_id (int): the ID of the ip address to update
        note (str): the text to add to the notes field

    """
    return client.call('Network_Subnet_IpAddress', 'editObject',{'note':note} ,id=ip_id)

def update_note_on_subnet(subnet_id, note=None):
    """Updates the notes field of a subnet in Softlayer.

    Args:
        subnet_id (int): the ID of the subnet to update
        note (Optional[str]): Defaults to None and uses the text 'dashDB Portable Subnet in that case.  the text to add to the notes field
    """
    if note is None:
        note = 'dashDB Portable Subnet'
    return client.call('Network_Subnet', 'editNote', note, id=subnet_id)

###########
# Takes an initialized SoftLayer client
def get_ips_in_subnet(subnet_id):
    """Gets a list of list of IP objects in json form given a subnet ID.

    Args:
        subnet_id (int): the ID of the subnet to list IPs

    Returns:
        str: list of IP objects in json form

    """
    ips = client.call('Network_Subnet', 'getIpAddresses', id=subnet_id, mask="id, ipAddress, isBroadcast, isGateway, isNetwork, isReserved, note")
    return ips

# Copied from https://github.com/softlayer/softlayer-python/blob/master/SoftLayer/managers/vs.py
# Adapted for Hardware
def wait_for_ready(instance_id, limit, delay=1):
    """Determine if a bare metal server is ready and available.
    In some cases though, that can mean that no transactions are running.
    The default arguments imply a server is operational and ready for use by
    having network connectivity and remote access is available.

    Args:
        instance_id (int): The server ID with the pending transaction
        limit (int): The maximum amount of time to wait.
        delay (int): The number of seconds to sleep before checks. Defaults to 1.

    Example::

        # Will return once server 12345 is ready, or after 10 checks
        ready = wait_hw.wait_for_ready(12345, 10)

    """
    ## Bowen -- Dirty hack to make this work for hardware, just set pending
    ## to always be true (waill wait for ALL transactions, good thing SL just
    ## got rid of their monitoring for hardware...
    pending = True
    until = time.time() + limit
    for new_instance in itertools.repeat(instance_id):
        mask = """id, lastOperatingSystemReload.id, activeTransaction.id,provisionDate"""
        instance = bm.get_hardware(new_instance, mask=mask)
        last_reload = utils.lookup(instance, 'lastOperatingSystemReload', 'id')
        active_transaction = utils.lookup(instance, 'activeTransaction', 'id')

        reloading = all((
                active_transaction,
                last_reload,
                last_reload == active_transaction,
        ))

        # only check for outstanding transactions if requested
        outstanding = False
        if pending:
            outstanding = active_transaction

        # return True if the instance has only if the instance has
        # finished provisioning and isn't currently reloading the OS.
        if all([instance.get('provisionDate'), not reloading, not outstanding]):
            return True

        now = time.time()
        if now >= until:
            return False

        time.sleep(min(delay, until - now))

def reload_server(endpoint, server, image_id):
    """Perform an OS reload of a system (hardware or virtual). This ws taken from
    the offical Softlayer API for VM reloading and adapted to work for either

    Args:
        endpoint (str): Should be 'Hardware_Server' or 'Virtual_Guest'
            to correspond to the correct type of system you're reloading
        server (int): the virtual or hardware ID to reload
        image_id (int): The ID of the image to load onto the server

    Raises:
        SoftLayer.exceptions.SoftLayerAPIError

    """
    config = {}
    config['imageTemplateId'] = image_id
    return client.call(endpoint,'reloadOperatingSystem', 'FORCE', config, id=server)

def deploysmalltestvm(hostname, dc, publicvlan, privatevlan):
    """Deploys a small test VM in a target vlan for testing network connectiity.  Mostly for
    testing portable IPs when we don't have a trusted system in the VLAN we can manipulate.

    Waits for the VM to become available then returns the vsi details for the device.

    Args:
        dc (str): the datacenter, like `dal09` or `lon02`
        publicvlan (int): the ID number of the public vlan to deploy into
        privatevlan (int): the ID number of the private vlan to deploy into

    Returns:
        json: the VSI details from a get_instance call to the Softlayer API

    """
    new_vsi = {
              'hostname': hostname,
              'domain': 'cdsdev.net',
              'cpus': 1,
              'memory': 1024,
              'hourly': True,
              'os_code': 'CENTOS_LATEST',
              'local_disk': False,
              'disks': ['25'],
              'public_vlan': publicvlan,
              'private_vlan': privatevlan,
              'datacenter': dc
          }
    vsi = mgr.create_instance(**new_vsi)
    if DEBUG:
        print vsi
    mgr.wait_for_ready(vsi['id'], 3600, pending=True)
    details = mgr.get_instance(vsi['id'])
    if DEBUG:
        print details
    return details

def destroycci(instanceid):
    """Returns a VM.

    Args:
        instanceid (int): a CCI instance ID to return (not a bare metal!!).

    """
    print 'Cancelling instance ID %s' % instanceid
    mgr.cancel_instance(instanceid)

def get_cci_default_root_pw(instanceid):
    """Gets the root password that Softlayer has stored in their records.

    Args:
        instanceid (int): a CCI instance ID (not bare metal).

    """
    details = mgr.get_instance(instanceid)
    return details['operatingSystem']['passwords'][0]['password']

def get_hw_default_root_pw(instanceid):
    """Gets the root password that Softlayer has stored in their records for Bare Metal Hosts.

    Args:
        instanceid (int): a Bare Metal instance ID (not CCIs)

    """
    details = bm.get_hardware(instanceid)
    return details['operatingSystem']['passwords'][0]['password']

def get_vlan_details(vlan_id):
    """Gets vlan details

    Args:
        vlan_id (str): the id of the vlan

    Returns:
        json: details about the vlan in question

    """
    DEFAULT_GET_VLAN_MASK = ','.join([
            'firewallInterfaces',
            'primaryRouter[id, fullyQualifiedDomainName, datacenter]',
            'totalPrimaryIpAddressCount',
            'networkSpace'
    ])
    return net.vlan.getObject(id=vlan_id, mask=DEFAULT_GET_VLAN_MASK)

def get_subnet_details(subnet_id):
    """Gets subnet details

    Args:
        subnet_id (str): the id of the subnet

    Returns:
        json: details about the subnet in question

    """
    return net.get_subnet(subnet_id)

def check_dns_for_ip(ip):
    """Checks DNS for a pre-existing record with the IP address in it.  If found
    returns the hostname associated with it else it returns `None`

    Args:
        ip (str): the ip to check

    Returns:
        str: the hostname associated with the ip address in DNS or `None` if not found

    """
    zones = [ ZONE_ID_LON, ZONE_ID_DAL, ZONE_ID_SYD ]
    for zone in zones:
        result = check_dns_zone_for_ip(ip, zone)
        if result is not None:
            return result
    return None

def get_systems_by_base_hostname(base_hostname):
    """Searches for hosts by name `base_hostname*` in either VM or BareMetal
    and returns the list of SL systems matching that pattern.  If both VM and BM are found
    throws a SystemExit exception

    Args:
        base_hostname (str): the base name to search on for systems in softlayer

    Returns:
        dict: a dictionary of json entries corresponding to the SL hosts found keyed off each
            system's hostname

    Raises:
        SystemExit: If it finds both VMs and BareMetal with the same name it quits

    """
    systems = {}
    vms = mgr.list_instances(hostname='%s*' % base_hostname)
    bms = bm.list_hardware(hostname='%s*' % base_hostname)
    if len(bms) > 0 and len(vms) > 0:
        print 'ERROR: Found both virtual machines and bare metal systems for %s' % base_hostname
        exit(1)
    for vm in vms:
        vm['vm'] = True
    for hw in bms:
        hw['vm'] = False
    if len(vms) > 0:
        systems = {vm['hostname']: vm for vm in vms}
    if len(bms) > 0:
        systems = {hw['hostname']: hw for hw in bms}
    return systems

def get_systems_by_domain(domain):
    """Gets a dictionary of all systems by domain name in the account.  Dicitonary is of hostname : details

    Args:
        domain (str): the domain to lookup

    Returns:
        dictionary: a hostname to softlayer details dictionary

    """
    systems = {}
    vmsystems = {}
    bmsystems = {}
    vms = mgr.list_instances(domain=domain)
    bms = bm.list_hardware(domain=domain)
    for vm in vms:
        vm['vm'] = True
    for hw in bms:
        hw['vm'] = False
    if len(vms) > 0:
        vmsystems = {vm['hostname']: vm for vm in vms}
    if len(bms) > 0:
        bmsystems = {hw['hostname']: hw for hw in bms}
    systems = vmsystems.copy()
    systems.update(bmsystems)
    return systems

def check_dns_zone_for_ip(ip, zone):
    """Checks a DNS zone for a record that points to an specified IP.  If found returns the
    host it is associated with, else it returns `None`

    Args:
        ip (str): the ip to check
        zone (int): the zone_id of the zone to check

    Returns:
        str: the host associated with the ip address in the DNS zone or `None` if not found

    """
    global dnsrecords
    if dnsrecords.has_key(zone):
        records = dnsrecords[zone]
    else:
        try:
            records = dns.get_records(zone)
        except SoftLayerAPIError:
            if DEBUG:
                print 'Unable to get DNS records for zone ID %s' % zone
            records = []
        dnsrecords[zone] = records
    for record in records:
        if record['data'] == ip:
            if DEBUG:
                print 'Found DNS record %s %s' % (record['host'] , ip)
            return record['host']
    return None

def get_dc_city(dc):
    """Takes a datacenter shortname and returns a lowercase city name where that datacenter resides.
    Useful for populating `dynamite-controller`'s `monitoring.region`

    Args:
        dc (str): datacenter short name: Dal09, par01, etc

    Returns:
        str: lowercase city name where the datacenter is

    """
    dc = dc.lower()
    longname = None
    try:
        datacenters = client.call('Location_Datacenter', 'getDatacenters')
    except SoftLayer.SoftLayerError:
        print 'ERROR: Received SoftLayer exception!'
        return
    for datacenter in datacenters:
        if dc == datacenter['name']:
            longname = datacenter['longName']

    if longname == None:
        return
    name = ''.join([i for i in longname if i.isalpha()])
    name = name.lower()
    return name

def get_dash_swift_endpoint(dc):
    """Takes a datacenter shortname and returns a dashDB swift endpoint.

    Args:
        dc (str): datacenter short name: Dal09, par01, etc.

    Returns:
        str: swift endpoint for softlayer backups

    """
    dc = dc.lower()
    city = get_dc_city(dc)
    if city is None:
        return
    # Deal with special cases for US-Fed
    if dc == "dal08" or dc == "wdc03":
        swiftdc = dc
    else:
        swiftdc = SWIFT_DC_MAPPING[city]
    swift_endpoint = 'https://%s.objectstorage.service.networklayer.com/auth/v1.0' % swiftdc
    return swift_endpoint

def get_dash_logging_region(dc):
    """Takes a datacenter shortname and returns the closest bluemix region (logging region)

    Args:
        dc (str): datacenter short name: Dal09, par01, etc.

    Returns:
        str: closest bluemix region (logging region) ex: Sydney, US_South, United_Kingdom

    """
    city = get_dc_city(dc)
    if city is None:
        return
    return SL_TO_BLUEMIX_MAPPING[city]

def generate_backup_time_mappings():
    """Generates a mapping (to stdout) of cities -> backup time starts (for property setting in UCD).

    """
    try:
        datacenters = client.call('Location_Datacenter', 'getDatacenters')
        dcs = {''.join([i for i in x['longName'] if i.isalpha()]).lower(): x for x in datacenters}
        for key in dcs.keys():
            dc = dcs[key]
            timezone = client.call('Location_Datacenter', 'getTimezone', id=dc['id'])
            local_backup_time = 200
            offset = int(timezone['offset'])
            backup_time = int((local_backup_time - offset) / 100)
            if backup_time < 0:
                backup_time = backup_time + 24
            print '\'{:<}\' : \'{:<}\','.format(key, backup_time)
    except SoftLayer.SoftLayerError:
        print 'ERROR: Received SoftLayer exception!'
        return
