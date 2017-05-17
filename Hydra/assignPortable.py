#!/usr/bin/python
import argparse,sys,json,os,SoftLayer
from SoftLayer import NetworkManager
from SoftLayer import utils
from cloudant.client import CouchDB
import json
import subprocess
from subprocess import PIPE

def main(argv):
    parser = get_parser()
    args = parser.parse_args()
    args.func(args)

def get_parser():
    parser = argparse.ArgumentParser(description='Main entry point for manipulating SoftLayer portable IPs')
    subparsers = parser.add_subparsers(title='subcommands', description='valid subcommands', help='additional help')

    # parser_order = subparsers.add_parser('order', help='order subnet of ips')
    # parser_order.set_defaults(func=order)

    parser_scan = subparsers.add_parser('scan', help='scan for portable ip subnets marked Hydra Only')
    parser_scan.set_defaults(func=scan)

    parser_pool = subparsers.add_parser('pool', help='call hit script to pool portable ips into target cluster')
    parser_pool.set_defaults(func=pool_ips)

    parser_update = subparsers.add_parser('update', help='pulls current ip information and push into console')
    parser_scan.add_argument('--newcluster', default=False, action='store_true', help='will update if there is a new cluster')
    parser_update.set_defaults(func=query_managepip)

    parser_pool = subparsers.add_parser('delete', help='delete ips from cloudant repo')
    parser_pool.set_defaults(func=delete_ip)

    return parser

def connectCouchDB():
    """Connect to Cloudant Repo"""
    global client

    # set this as env variable as well if too sensitive
    USERNAME='ttermserseentsmistellacq'
    PASSWORD='fad461f53aec6a2faaf7b21eb402c4684b6723b1'

    # USERNAME = os.environ.get('CLOUD_UN')
    # PASSWORD = os.environ.get('CLOUD_PW')
    ACCOUNT='https://dhurng.cloudant.com'

    client = CouchDB(USERNAME, PASSWORD, url=ACCOUNT)
    client.connect()
    session = client.session()

    connectPortIPDB()

def connectPortIPDB():
    """Connect to portableip database in Cloudant"""
    global portable_ip_db
    portable_ip_db = client['portableip']

    if portable_ip_db.exists():
        print "Connection to portableiP Database made"
    else:
        print "DataBase does not exist"

def connectSL():
    """Connect to SoftLayer account via env variables"""
    global slclient
    global networkMan

    slid = os.environ.get('SL_USERNAME')
    slapikey = os.environ.get('SL_API_KEY')
    slclient = SoftLayer.create_client_from_env(username=slid, api_key=slapikey)

    try:
        account = slclient['Account'].getObject()
        print "SL account: " + slid
        networkMan = SoftLayer.NetworkManager(slclient)
    except SoftLayer.SoftLayerAPIError as e:
        print("Unable to retrieve account information faultCode=%s, faultString=%s"
              % (e.faultCode, e.faultString))
        exit(1)

def update_note_on_ip(args):
    """Updates the notes field of an IP address in Softlayer.
    Args:
        ip_id (int): the ID of the ip address to update
        note (str): the text to add to the notes field
    """
    connectSL()
    file = raw_input('Enter a filename of ips: ')
    note = raw_input("What will these ips be used for?: ")

    try:
        data = json.load(open(file))
        for p in data['info']:
            print "Updating ", p['_id'], " with ", note
            ip_id = p['ip_id']
            print "******"
            print slclient.call('Network_Subnet_IpAddress', 'editObject', {'note':note}, id=ip_id)#
    except:
        with open(file) as f:
            content = f.readlines()
            for x in content:
                ip = x.strip()
                print ip
                info = networkMan.ip_lookup(ip)
                ip_id = info['id']
                print "ID:", ip_id
                print slclient.call('Network_Subnet_IpAddress', 'editObject', {'note':note}, id=ip_id)

def not_response(prompt, index):
    """Makes sure the selections are valid during gui interaction"""
    while True:
        try:
            value = int(input(prompt))
        except IndexError:
            print "Index out of range"
            continue
        if value >= index:
            print "Choose within range please"
            continue
        else:
            break
    return value

def vlan_num_to_id(vlannum):
    """SoftLayer uses vlan numbers (ex. 1385) in cds-dev and
     vlan ids (ex. 1391061) which we need for api
    Args:
        vlannum (int): the vlan number user enters
    Returns:
        ids (list): list of potential vlans with associated SL ids
     """
    print "***VLAN INFO***"
    list = networkMan.list_vlans(None, vlannum, None)
    i = 0
    for item in list:
        print "{:d}:".format(i), item
        i += 1
    print "***************"
    prompt = "Specify which VLAN (0 index): "
    i = not_response(prompt, i)
    return list[i]['id']

def get_hydra_portable_subnets(vlanid):
    """Finds all portable subnets in a given VLAN that are marked as suitable for hydra use.
      Expects portable subnets that are for hydra use to have 'Hydra Only' in their notes field
      and will ignore any that do not have that exactly.
      Args:
          vlan (int): the vlan id to search for portabe subnets
      Returns:
          json: a list of portable subnets for hydra use.
      """
    filter = utils.NestedDict({})
    filter['subnets']['note']['operation'] = "Hydra Only"
    filter['subnets']['subnetType']['operation'] = "SECONDARY_ON_VLAN"
    filter['subnets']['networkVlanId']['operation'] = vlanid

    return networkMan.list_subnets(filter=filter.to_dict())

def report(list, vlan):
    """
    Creates new output file with JSON data of the ips found
    Args:
        list (list): list of ips in doc structure
        vlan (int): vlan number
        vlanid (int): id of the corresponding vlan
        subnets (list): list of subnets
    Returns:
        output (file): target file in json format
    """
    print "***************"
    print_paper = []
    for ip in list:
        ipAddress = ip['ipAddress']
        print ipAddress
        dict = {'_id': ipAddress, 'exists': 1, 'empty': 1, 'service': "", 'vlan': vlan}
        add_ip_db(dict)
        print_paper.append(ipAddress)

    file = raw_input("Specify output file: ")
    if not file:
        exit()
    else:
        with open(file, 'w+') as outfile:
            for ip in print_paper:
                outfile.write("%s\n" % ip)

def get_ips_in_subnet(subnet_id):
    """Gets a list of list of IP objects in json form given a subnet ID.
       Args:
           subnet_id (int): the ID of the subnet to list IPs
       Returns:
           str: list of IP objects in json form
       """
    ips = slclient.call('Network_Subnet', 'getIpAddresses', id=subnet_id,
                      mask="id, ipAddress, isBroadcast, isGateway, isNetwork, isReserved, note")
    return ips

# """
# Orders a new subnet
# Args:
#     subnet_type - type or subnet (private | public | global)
#     quantity - number of ips in subnet (4 | 8 | 16 | 32)
#     vlan_id - vlan id for subnet to be in
#     version - 4 for IPv4, 6 for IPv6
#     test_order - if true it will only verify the order
# """
# def order(args):
#     connectSL(slid=args.slid, slapikey=args.slkey)
#     print "***************"
#     sub_type = raw_input("what type of subnet? (public | private | global): ")
#     vlan = input("Specify Backend or Frontend VLAN you want to order for: ")
#     vlanid = vlan_num_to_id(vlan)
#     quantity = input("How many ips do you want to order: ")
#     version = input("What version (4 = IPv4 || 6 = IPv6): ")
#     print networkMan.add_subnet(sub_type, quantity, vlanid, version, test_order=True)

def scan(args):
    """Scans the vlan for subnets marked Hydra Only"""
    connectSL()
    connectCouchDB()

    print "***************"
    vlan = input("Specify Backend or Frontend VLAN: ")
    vlanid = vlan_num_to_id(vlan)
    subnets = get_hydra_portable_subnets(vlanid)
    print 'Found %s portable subnets in vlan # %s marked Hydra Only' % (len(subnets), vlan)
    managed = []
    i = 0
    for subnet in subnets:
        print "{:d}:".format(i), subnet['networkIdentifier']
        i += 1
    prompt = "Specify which Subnet: "
    i = not_response(prompt, i)
    ips = get_ips_in_subnet(subnets[i]['id'])
    for ip in ips:
        if not ip['isReserved'] and not ip['isBroadcast'] and not ip['isNetwork'] and not ip['isGateway']:
             managed.append(ip)
    report(managed, vlan)

    client.disconnect()

def delete_ip(args):
    """Delete the ips from the cloudant repo, most likely when subnet is cancelled/returned"""
    connectCouchDB()
    file = raw_input('Enter a filename of ips: ')
    with open(file) as json_file:
        data = json.load(json_file)
        for p in data['info']:
            try:
                if portable_ip_db[p['_id']]:
                    print p['_id'], "In Repo"
                    doc = portable_ip_db[p['_id']]
                    print doc['_id'], " Deleting"
                    doc.delete()
            except KeyError:
                print "Not within Repo "
    client.disconnect()

"""
Can also use etcd to push via api
"""
def pool_ips(args):
    file = raw_input('Enter a filename of ips to pool: ')
    if os.path.isfile('./managePip') and os.path.isfile('./managePip.sh') and os.path.isfile(file):
        output = subprocess.Popen("./managePip -d -a listPipDetails", shell=True, stdout=PIPE, stderr=PIPE)
        # checkoutput
    else:
        print "Files Not Found"

def add_ip_db(dict):
    try:
        if portable_ip_db[dict['_id']]:
            if str(dict['exists']) == str(portable_ip_db[dict['_id']]['exists']) and \
                            str(dict['empty']) == str(portable_ip_db[dict['_id']]['empty']) and \
                            str(dict['service']) == str(portable_ip_db[dict['_id']]['service']):
                print "Up-to-date"
            else:
                print "UPDATING"
                doc = portable_ip_db[dict['_id']]
                doc['exists'] = dict['exists']
                doc['empty'] = dict['empty']
                doc['service'] = dict['service']
                doc.save()
                print doc
    except KeyError:
        print "Not within Repo..Adding"
        doc = portable_ip_db.create_document(dict)
        print doc

def query_managepip(args):
    # grab private ip from the hosts file from fr8r dir
    # curl --cert ${ADMIN_CERTS}/etcd.pem --key ${ADMIN_CERTS}/etcd-key.pem --cacert ${ADMIN_CERTS}/ca.pem https://PRIVATE IP:9999/v2/keys/softlayer
    # portable/subnets/list of ips and their services
    # parse the info into dictionaries

    # if the new option is used
    # Request github link of host file of new cluster
    # get the private ip of master node

    # hard code for default
    github_link = ""
    if args.newcluster:
        new_link = raw_input('Enter github link to host file: ')


    if os.path.isfile('./managePip') and os.path.isfile('./managePip.sh'):
        connectCouchDB()
        res = []
        my_dict = {}
        output = subprocess.Popen("./managePip -d -a listPipDetails",shell=True, stdout=PIPE, stderr=PIPE)
        data = output.communicate()[0].split('\n')
        for line in data:
            if line.strip():
                result = line.split(':')
                print result
                pip = result[0]
                exists = result[1]
                empty = result[2]
                service = result[6]
                service = service.strip()
                service = service.split('}')
                service = service[0]
                # how to determine vlan from given ip?
                dict = {'_id': pip, 'exists': exists, 'empty': empty, 'service': service, 'vlan':""}
                add_ip_db(dict)
        client.disconnect()
    else:
        print "No manage script within dir"

if __name__ == '__main__':
   main(sys.argv[1:])
