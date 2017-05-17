#!/usr/bin/python
import json,os,sys,argparse,math
from softlayer import sl
from ucd import cli

DELAY = 2 # 2 second delay between SL calls
DEBUG = False

SMP_SVCPLAN = {
    'TXN: Small' : 'cds:svcplan:txn',
    'TXN: Large' : 'cds:svcplan:txn',
    'TXNHA: Small' : 'cds:svcplan:txnha',
    'TXNHA: Large' : 'cds:svcplan:txnha',
    'TXN: Flex' : 'cds:svcplan:txnflex',
    'TXNHA: Flex' : 'cds:svcplan:txnhaflex',
    'TXN: XLarge' : 'cds:svcplan:txn',
    'TXNHA: XLarge' : 'cds:svcplan:txnha',
    '12TB' : 'cds:svcplan:enterprise',
    '4TB' : 'cds:svcplan:enterprise',
    '1TB' : 'cds:svcplan:enterprise',
    '1TB: Entry (Testing)' : 'cds:svcplan:entry',
    'Entry' : 'cds:svcplan:entry',
    'TestVM: Entry' : 'cds:svcplan:entry',
    'TestVM: Enterprise' : 'cds:svcplan:enterprise'
}

SMP_PATTERN = {
    'TXN: Small' : 'production.8.500.template.txn',
    'TXN: Large' : 'production.128.1.6TB.txn',
    'TXNHA: Small' : 'production.hadr.8.500GB.template.txn',
    'TXNHA: Large' : 'production.hadr.128.1.6TB.txn',
    'TXN: Flex' : 'production.txn.flex',
    'TXNHA: Flex' : 'production.txnha.flex',
    'TXN: XLarge' : 'production.48.1000.12TB.txn',
    'TXNHA: XLarge' : 'production.hadr.48.1000.12TB.txn',
    '12TB' : 'production.12TB',
    '4TB' : 'production.4TB.4850',
    '1TB' : 'production.1TB',
    '1TB: Entry (Testing)' : 'production.1TB',
    'Entry' : 'production.Entry',
    'TestVM: Entry' : 'SmallTestVM',
    'TestVM: Enterprise' : 'SmallTestVM'
}

SMP_FEDERAL_PATTERN = {
    '4TB' : 'production.4TB.FED',
    '1TB' : 'production.1TB.fed'
}

SMP_DSSERVER_CONFIG = {
    'TXN: Small' : 'bluemix.medium',
    'TXN: Large' : 'bluemix.medium',
    'TXNHA: Small' : 'bluemix.medium',
    'TXNHA: Large' : 'bluemix.medium',
    'TXN: Flex' : 'bluemix.medium',
    'TXNHA: Flex' : 'bluemix.medium',
    'TXN: XLarge' : 'bluemix.medium',
    'TXNHA: XLarge' : 'bluemix.medium',
    '12TB' : 'bluemix.medium',
    '4TB' : 'bluemix.medium',
    '1TB' : 'bluemix.medium',
    '1TB: Entry (Testing)' : 'bluemix.small',
    'Entry' : 'bluemix.small',
    'TestVM: Entry' : 'bluemix.small',
    'TestVM: Enterprise' : 'bluemix.medium'
}

SMP_BLUEPRINT = {
    'TXN: Small' : 'dashDB-txn',
    'TXN: Large' : 'dashDB-txn',
    'TXNHA: Small' : 'dashDB-txnha',
    'TXNHA: Large' : 'dashDB-txnha',
    'TXN: Flex' : 'dashDB-txn',
    'TXNHA: Flex' : 'dashDB-txnha',
    'TXN: XLarge' : 'dashDB-txn',
    'TXNHA: XLarge' : 'dashDB-txnha',
    '12TB' : 'dashDB',
    '4TB' : 'dashDB',
    '1TB' : 'dashDB',
    '1TB: Entry (Testing)' : 'dashDB',
    'Entry' : 'dashDB',
    'TestVM: Entry' : 'dashDB',
    'TestVM: Enterprise' : 'dashDB'
}

SMP_PLAN_HOSTNAME = {
    'TXN: Small' : 'txn-small',
    'TXN: Large' : 'txn-large',
    'TXNHA: Small' : 'txnha-small',
    'TXNHA: Large' : 'txnha-large',
    '12TB' : 'enterprise12',
    '4TB' : 'enterprise4',
    '1TB' : 'enterprise',
    '1TB: Entry (Testing)' : 'entry',
    'Entry' : 'entry',
    'TestVM: Entry' : 'testvm',
    'TestVM: Enterprise' : 'testvm'
}

MPP_BLUEPRINT = {
    'Regular Node BM' : 'Dynamite-MPP-{}node-Softlayer',
    'Regular Node VM' : 'Dynamite-MPP-{}node-Softlayer',
    'Regular Node VM CentOS 7' : 'Dynamite-MPP-{}node-Softlayer',
    'Super Node BM' : 'Dynamite-MPP-{}node-Softlayer',
    'Super Node VM' : 'Dynamite-MPP-{}node-Softlayer',
    'Regular Node 64GB VM' : 'Dynamite-MPP-{}node-Softlayer',
    'Super Node BM Backup' : 'Dynamite-MPP-{}backupnode-Softlayer',
    'Super Node VM Backup' : 'Dynamite-MPP-{}backupnode-Softlayer'
}

MPP_PATTERN = {
    'Regular Node BM' : 'MPP{}NodePatternBM',
    'Regular Node VM' : 'MPP{}NodePattern',
    'Regular Node VM CentOS 7' : 'dashDB-mpp-{}node',
    'Super Node BM' : 'MPP{}SuperNodesBM',
    'Super Node VM' : 'MPP{}SuperNodes',
    'Regular Node 64GB VM' : 'MPP{}NodePattern64GB',
    'Super Node BM Backup' : 'MPP{}SuperNodesBM-backup',
    'Super Node VM Backup' : 'MPP{}SuperNodes-backup'
}

BMIXENV = {
    'US_South' : {
        'YP' : 'cds:bmixenv:yp',
        'YS1' : 'cds:bmixenv:ys1',
        'Dev' : 'cds:bmixenv:cdsdev',
        'Test' : 'cds:bmixenv:cdsdev'
    },
    'Sydney' : {
        'YP' : 'cds:bmixenv:syp',
        'YS1' : 'cds:bmixenv:ys1',
        'Dev' : 'cds:bmixenv:cdsdev',
        'Test' : 'cds:bmixenv:cdsdev'
    },
    'United_Kingdom' : {
        'YP' : 'cds:bmixenv:lyp',
        'YS1' : 'cds:bmixenv:lys1',
        'Dev' : 'cds:bmixenv:cdsdev',
        'Test' : 'cds:bmixenv:cdsdev'
    }
}

degraded_networking = ['ams01', 'hkg02', 'sao01', 'sng01', 'wdc01']

degraded_networking_overrides = {
    'production.4TB.4850' : 'production.4TB.4850.degraded.network'
}

def main(argv):
    global DEBUG
    parser = get_parser()
    args = parser.parse_args()

    DEBUG = args.debug
    cli.DEBUG = args.debug

    if args.slid is not None:
        sl.set_creds(args.slid, args.slapi)

    if args.token is not None:
        cli.set_token(args.token)

    # Get the deployment environment details
    props = cli.get_component_env_props('dynamite-controller', args.environment)

    resource = '/CDS dashDB/%s' % args.environment
    # Determine the initial build location
    if props['env.type'] == 'YP':
        # Production, we build in the staging area
        resource = cli.get_app_prop('new.deployment.staging.area')

    print 'InitialBuildPath=%s' % resource

    # Do any SMP/MPP specific pre-deployment steps
    args.func(args, props)

def get_parser():
    parser = argparse.ArgumentParser(description='This is the pre-deployment script that generates various metadata used for deployment and property setting steps used in the initial deployment process.')
    parser.add_argument('-t', '--token', help='UCD Token')
    parser.add_argument('-i', '--slid', help='SL ID')
    parser.add_argument('-k', '--slapi', help='SL API Key')
    parser.add_argument('-d', '--debug', default=False, action='store_true', help='Turns on additional debug logging')
    parser.add_argument('-a', '--assign-hostname', default=False, action='store_true', help='Assigns a hostname')
    parser.add_argument('-c', '--callback', help='Process ID for setting the pattern property')
    parser.add_argument('environment', help='The name of the deployment environment')
    parser.add_argument('--trial', help='for marking production deployments as trial systems', default=False, action='store_true')

    subparsers = parser.add_subparsers(title='subcommands', description='valid subcommands', help='additional help')

    parser_smp = subparsers.add_parser('smp', help='SMP specific pre-deployment')
    parser_smp.add_argument('smptype', help='type of deployment for the target environment', choices=['TXN: Small', 'TXN: Large', 'TXNHA: Small', 'TXNHA: Large', 'TXN: Flex', 'TXNHA: Flex', 'TXN: XLarge', 'TXNHA: XLarge', '12TB', '4TB', '1TB', 'Entry', 'TestVM: Entry', 'TestVM: Enterprise', '1TB: Entry (Testing)'])
    parser_smp.set_defaults(func=smp_pre_deploy)

    parser_mpp = subparsers.add_parser('mpp', help='MPP specific pre-deployment')
    parser_mpp.add_argument('nodes', type=int, help='Number of nodes in the mpp configuration')
    parser_mpp.add_argument('config', help='Node configuration type (production, testvms, supernode, etc)')
    parser_mpp.add_argument('contact', help='User to contact for mpp node config template generation')
    parser_mpp.add_argument('--nodeid', type=int, help='Override the starting ID for the node count')
    parser_mpp.set_defaults(func=mpp_pre_deploy)

    parser_aws = subparsers.add_parser('aws', help='AWS specific pre-deployment')
    parser_aws.set_defaults(func=aws_pre_deploy)

    return parser

def smp_pre_deploy(args, parentprops):
    svcplan = SMP_SVCPLAN[args.smptype]
    dsserverconfig = SMP_DSSERVER_CONFIG[args.smptype]
    blueprint = SMP_BLUEPRINT[args.smptype]
    slpp = smppattern(args.smptype, parentprops)

    bmixenv = getbmixenv(parentprops)
    if args.trial:
        svcenv = 'cds:svcenv:trials'
    else:
        svcenv = getsvcenv(args.environment, parentprops)

    softlayertags = 'cds:service:dash;%s;%s;%s' % (svcplan, bmixenv, svcenv)

    if args.assign_hostname:
        hostname = get_hostname(parentprops, SMP_PLAN_HOSTNAME[args.smptype])
        print 'Hostname=%s' % hostname

    print 'DsserverConfig=%s' % dsserverconfig
    print 'SoftlayerTags=%s' % softlayertags
    print 'ProvisioningBlueprint=%s' % blueprint
    print 'SoftlayerProvisioningPattern=%s' % slpp

def mpp_pre_deploy(args, parentprops):
    role = 'node'
    if args.config.endswith('Backup'):
        role = 'backup'

    if not MPP_BLUEPRINT.has_key(args.config):
        print 'ERROR: Unable to find blueprint mapping for %s' % args.config
        exit(1)
    if not MPP_PATTERN.has_key(args.config):
        print 'ERROR: Unable to find pattern mapping for %s' % args.config
        exit(1)

    bmixenv = getbmixenv(parentprops)
    if args.trial:
        svcenv = 'cds:svcenv:trials'
    else:
        svcenv = getsvcenv(args.environment, parentprops)

    backup_nodes = int(math.ceil(float(args.nodes) / 5.0))
    blueprint_nodes = args.nodes
    if role == 'backup':
        blueprint_nodes = backup_nodes
    blueprint = MPP_BLUEPRINT[args.config].format(blueprint_nodes)
    slpp = MPP_PATTERN[args.config].format(args.nodes)
    svcplan = 'cds:svcplan:mpp'
    if 'super' in args.config.lower():
        svcplan = 'cds:svcplan:supernode'

    if args.assign_hostname:
        hostname = get_hostname(parentprops, 'mpp')
        print 'Hostname=%s' % hostname

    nodeid = 1
    if args.nodeid is not None:
        nodeid = args.nodeid
    softlayertags = 'cds:service:dash;%s;%s;%s' % (bmixenv, svcenv, svcplan)
    print 'SoftlayerTags=%s' % softlayertags
    print 'ProvisioningBlueprint=%s' % blueprint
    print 'SoftlayerProvisioningPattern=%s' % slpp
    print 'NumberOfNodes=%s' % args.nodes
    print 'NumberOfBackupNodes=%s' % backup_nodes

    node_config = cli.generate_sl_mpp_json(args.contact, args.config, args.nodes, role=role, nodeid_start=nodeid)

    if args.callback is not None:
        cli.setapplicationprop_by_rest(args.callback, json.dumps(node_config))

def aws_pre_deploy(args, parentprops):
    if args.trial:
        svcenv = 'trials'
    else:
        svcenv = getawssvcenv(args.environment, parentprops)

    if args.assign_hostname:
        hostname = get_hostname(parentprops, 'mpp')
        print 'Hostname=%s' % hostname

    print 'AWSTags=%s' % svcenv

def smppattern(smptype, parentprops):
    if parentprops['federal'] == 'true':
        if SMP_FEDERAL_PATTERN.has_key(smptype):
            return SMP_FEDERAL_PATTERN[smptype]
        else:
            print 'US-Fed environment detected and I cannot find a federal softlayer pattern for deployment type %s' % smptype
            raise SystemExit(1)
    slpp = SMP_PATTERN[smptype]
    if parentprops['DC'].lower() in degraded_networking and degraded_networking_overrides.has_key(slpp):
        slpp = degraded_networking_overrides[slpp]
    return slpp # TO DO replace this with something better that creates patterns on the fly from the SL api

def getsvcenv(env, props):
    mapping = {
        'YP' : 'cds:svcenv:prod',
        'YS1' : 'cds:svcenv:prod',
        'Dev' : 'cds:svcenv:dev',
        'Test' : 'cds:svcenv:qa'
    }

    svcenv = mapping[props['env.type']]
    if 'Staging' in env:
        svcenv = 'cds:svcenv:ops_stage'

    return svcenv

def getawssvcenv(env, props):
    mapping = {
        'YP' : 'prod',
        'YS1' : 'prod',
        'Dev' : 'dev',
        'Test' : 'qa'
    }

    svcenv = mapping[props['env.type']]
    if 'Staging' in env:
        svcenv = 'ops_stage'

    return svcenv

def getbmixenv(props):
    bmixenv = BMIXENV[props['logging_region']][props['env.type']]
    if props['dedicated.env'] == 'true':
        bmixenv = 'cds:bmixenv:dedicated'
    if props['hipaa'] == 'true':
        bmixenv += ';cds:compliance:hipaa'
    return bmixenv

def get_hostname(props, typetag):
    service = 'dashdb' # For now just hardcode this, may have to figure out dash15 at somepoint...
    #zonetag = props['zone.tag']
    zonetag = 'yp' # just hardcode this for now till I figure out how to populate this for everyone
    dc = props['DC'].lower()
    domain = props['domain']
    primative_base = '%s-%s-%s-%s' % (service, typetag, zonetag, dc)
    primative = primative_base + '-{:0=2}'
    if DEBUG:
        print 'hostname primative: %s' % primative_base

    hosts = sl.get_systems_by_base_hostname(primative_base)
    names = hosts.keys()
    if DEBUG:
        print 'checking Softlayer hosts for a free name:\n%s' % names
    for x in range(1, 1000):
        if not any(primative.format(x) in hostname for hostname in names):
        # Check this??!?! how?
            return primative.format(x)

if __name__ == "__main__":
    main(sys.argv[1:])
