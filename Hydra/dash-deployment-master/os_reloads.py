#!/usr/bin/python
import os,json,sys,argparse
import SoftLayer
from softlayer import sl
from ucd import cli
from multiprocessing.dummy import Pool as ThreadPool
from common import util

#######
DEBUG = False

blueprint_blacklist = ['toolserver', 'guardium', 'guardium-aws']
destroy_blacklist = ['toolserver']

txn_blueprints = ['dashDB-txn', 'dashDB-txn-reload', 'DB2onCloud', 'DB2onCloud-reload']

blueprinttypes = {
    'SMP'    : ['dashDB', 'dashDB-reload', 'dashDB-txn', 'dashDB-txn-reload', 'DB2onCloud', 'DB2onCloud-reload'],
    'HA'     : ['dashDB-txnha', 'DB2onCloud-HADR'],
    'MPP'    : 'Dynamite-MPP-',
    'Backup' : 'backupnode-Softlayer'
}

smp_blueprint_map = {
    'dashDB' : 'dashDB-reload',
    'dashDB-reload' : 'dashDB-reload',
    'dashDB-txn' : 'dashDB-txn-reload',
    'dashDB-txn-reload' : 'dashDB-txn-reload',
    'DB2onCloud' : 'dashDB-txn-reload',
    'DB2onCloud-reload' : 'dashDB-txn-reload'
}

ha_blueprint_map = {
    'dashDB-txnha' : 'dashDB-txnha',
    'DB2onCloud-HADR' : 'dashDB-txnha'
}

imagepropname = {
    'SMP' : {
        True  : 'softlayer.virtual.smp.template.id',
        False : 'softlayer.server.template.id'
    },
    'MPP' : {
        True  : 'softlayer.virtual.mpp.template.id',
        False : 'softlayer.server.template.id'
    },
    'Backup' : {
        True  : 'softlayer.server.template.id',
        False : 'softlayer.server.template.id'
    },
    'HA'  : {
        True  : 'softlayer.virtual.smp.template.id',
        False : 'softlayer.server.template.id'
    },
    'SMP-fed' : {
        True  : 'softlayer.fed.virtual.smp.template.id',
        False : 'softlayer.fed.server.template.id'
    },
    'MPP-fed' : {
        True  : 'softlayer.fed.virtual.mpp.template.id',
        False : 'softlayer.fed.server.template.id'
    },
    'Backup-fed' : {
        True  : 'softlayer.fed.server.template.id',
        False : 'softlayer.fed.server.template.id'
    },
    'HA-fed'  : {
        True  : 'softlayer.fed.virtual.smp.template.id',
        False : 'softlayer.fed.server.template.id'
    }
}

def main(argv):
    parser = get_parser()
    args = parser.parse_args()
    global DEBUG
    if args.dryrun:
        args.debug = args.dryrun

    if args.debug:
        print 'Debug output is ON'
        DEBUG = True
        cli.DEBUG = True
        sl.DEBUG = True

    sl.set_creds(args.slid, args.slkey)

    if args.ucdtoken is not None:
        cli.set_token(args.ucdtoken)

    if args.snapshot == 'None':
        args.snapshot = None

    rebuild(args)

def get_parser():
    parser = argparse.ArgumentParser(description='Recreates a dashDB Softlayer Environment.')
    parser.add_argument('-d', '--debug', default=False, action='store_true', help='Turns on additional debug logging')
    parser.add_argument('--destroy', default=False, action='store_true', help='Destroys Softlayer Virtual Guests and deletes the environment (no reload)')
    parser.add_argument('--dryrun', default=False, action='store_true', help='Enables debug output and stops short of reloading / destroying systems')
    parser.add_argument('-s', '--snapshot', default='None', help='Snapshot to use for redeploying dashDB.  If given the string "None", no attempt to redeploy will be made and system will be left blank.')
    parser.add_argument('-u', '--ucdtoken', help='UCD access token')
    parser.add_argument('parent', help='The name of the parent environment (where this is running)')
    parser.add_argument('target', help='The name of the environment to rebuild')
    parser.add_argument('slid', help='Softlayer id')
    parser.add_argument('slkey', help='Softlayer api key')

    return parser

def rebuild(args):
    target = args.target
    parent = args.parent
    parentprops = cli.get_component_env_props('dynamite-controller', parent)
    if DEBUG:
        print json.dumps(parentprops, sort_keys=True, indent=2)
    targetprops = cli.get_env_props(target)
    t_props = {n['name']: n['value'] for n in targetprops}
    if DEBUG:
        print json.dumps(t_props, sort_keys=True, indent=2)
    blueprint = ''
    reload_target = {}

    # Validate provider
    if parentprops['PROVIDER'] != 'SOFTLAYER':
        print 'ERROR: I can\'t reload %s systems' % parentprops['PROVIDER']
        exit(1)

    # Get blueprint
    try:
        blueprint = cli.get_env_blueprint(target)
    except KeyError:
        print 'ERROR: %s does not appear to have a blueprint, I\'m unable to rebuild that environment.' % target
        exit(1)

    # Validate parent / target environment
    if not target.startswith('%s-' % parent):
        print 'ERROR: %s is not the parent of %s by naming conventions' % (parent, target)
        exit(1)
    if not t_props.has_key('parent.env'):
        print 'WARNING: Unable to find parent.env from %s' % target
    elif t_props['parent.env'] != parent:
        print 'ERROR: %s is not the parent of %s according to %s\'s parent.env property' % (parent, target, target)
        exit(1)
    hostname_base = util.remove_prefix(target, '%s-' % parent)
    if DEBUG:
        print 'target = %s, parent = %s, hostname_base = %s' % (target, parent, hostname_base)

    # Get systems
    systems = sl.get_systems_by_base_hostname(hostname_base)
    if DEBUG:
        print 'Found %s systems of %s base hostname:' % (len(systems), hostname_base)
        print json.dumps(systems, sort_keys=True, indent=2)
    if len(systems) == 0:
        print 'ERROR: I found 0 systems matching the hostname %s' % hostname_base
        exit(1)
    reload_target['vm'] = systems.values()[0]['vm']

    # Validate the blueprint
    # Do the blacklist first
    if blueprint in blueprint_blacklist and not args.destroy:
        print 'ERROR: %s cannot be reloaded because it is a %s environment' % (target, blueprint)
        exit(1)
    if blueprint in destroy_blacklist and args.destroy:
        print 'ERROR: I can\'t let you do that dave.  Please destroy %s (a %s) manually.' % (target, blueprint)
        exit(1)

    # SMP blueprints
    elif blueprint in blueprinttypes['SMP']:
        if len(systems) != 1:
            print 'ERROR: %s has an SMP blueprint but I found %s systems with %s hostname base (expecting 1)' % (target, len(systems), hostname_base)
            exit(1)
        reload_target['blueprint'] = smp_blueprint_map[blueprint]
        reload_target['type'] = 'SMP'

    # HA blueprints
    elif blueprint in blueprinttypes['HA']:
        if len(systems) != 2:
            print 'ERROR: %s has an HA blueprint but I found %s systems with %s hostname base (expecting 2)' % (target, len(systems), hostname_base)
            exit(1)
        reload_target['blueprint'] = ha_blueprint_map[blueprint]
        reload_target['type'] = 'HA'

    # Backup blueprints
    elif blueprint.endswith(blueprinttypes['Backup']):
        node = 1
        while (node <= len(systems)):
            backuphost = '%s%s' % (hostname_base, node)
            if backuphost not in systems.keys():
                print 'ERROR: I found %s systems for %s but was unable to find %s, please examine the following hosts: %s' % (len(systems), hostname_base, backuphost, systems.keys())
                exit(1)
            node += 1
        tocheck = 'Dynamite-MPP-%sbackupnode-Softlayer' % len(systems)
        if not cli.blueprint_exists(tocheck):
            print 'ERROR: I found a %s node backup environment but no matching blueprint named %s' % (len(systems), tocheck)
            exit(1)
        reload_target['blueprint'] = tocheck
        reload_target['type'] = 'Backup'

    # MPP blueprints
    elif blueprint.startswith(blueprinttypes['MPP']):
        # Remove any backup nodes from the systems first
        backupnode = 1
        while (backupnode <= len(systems)):
            backuphost = '%s-backup%s' % (hostname_base, backupnode)
            if backuphost in systems.keys():
                del systems[backuphost]
            backupnode += 1

        if len(systems) < 3:
            print 'ERROR: Found an MPP environment but I did not find the minimum number of systems (require 3)'
            exit(1)
        node = 1
        while (node <= len(systems)):
            if '%s-node%s' % (hostname_base, node) not in systems.keys():
                print 'ERROR: I found %s systems for %s but was unable to find %s-node%s, please examine the following hosts: %s' % (len(systems), hostname_base, hostname_base, node, systems.keys())
                exit(1)
            node = node + 1
        tocheck = 'Dynamite-MPP-%snode-Softlayer' % len(systems)
        if not cli.blueprint_exists(tocheck):
            print 'ERROR: I found a %s node MPP cluster but no matching blueprint named %s' % (len(systems), tocheck)
            exit(1)
        reload_target['blueprint'] = tocheck
        reload_target['type'] = 'MPP'

    # /shrug
    else:
        print 'ERROR: I have no idea what %s is' % blueprint
        exit(1)


    ############################# DESTROY THE SYSTEMS ############################# 

    if args.dryrun and args.destroy:
        print 'Just a dry run!  Aborting now that we have collected and displayed what would have been...'
        raise SystemExit(0)

    if args.destroy:
        destroy_vms(systems, target)
        print 'Destroying UCD artifacts...'
        cli.delete_environment(target)
        exit()
    ############################# DESTROY THE SYSTEMS ############################# 

    # Figure out the Softlayer provisioning pattern or "sl-pp"
    slpp = ''
    if t_props.has_key('sl-pp'):
        slpp = t_props['sl-pp']

    if slpp == '' or reload_target['type'] != get_slpp_type(slpp):
        if slpp == '':
            print 'WARNING: %s is missing the property "sl-pp" will attempt to guess...' % target
        else:
            print 'WARNING: %s\'s existing sl-pp %s does not match the type of system this appears to be!  Attempting to guess a new one...' % (target, slpp)
        if reload_target['type'] == 'MPP' and reload_target['vm']:
            slpp = 'MPP3NodePattern'
        elif reload_target['type'] == 'MPP' and not reload_target['vm']:
            slpp = 'MPP3NodePatternBM'
        if reload_target['type'] == 'Backup' and reload_target['vm']:
            slpp = 'MPP3SuperNodes-backup'
        elif reload_target['type'] == 'Backup' and not reload_target['vm']:
            slpp = 'MPP3SuperNodesBM-backup'
        elif reload_target['type'] == 'HA' and reload_target['vm']:
            slpp = 'production.hadr.8.500GB.template.txn'
        elif reload_target['type'] == 'HA' and not reload_target['vm']:
            slpp = 'production.hadr.128.1.6TB.txn'
        elif reload_target['type'] == 'SMP' and reload_target['vm'] and blueprint in txn_blueprints:
            slpp = 'production.8.500.template.txn'
        elif reload_target['type'] == 'SMP' and not reload_target['vm'] and blueprint in txn_blueprints:
            slpp = 'production.128.1.6TB.txn'
        elif reload_target['type'] == 'SMP' and not reload_target['vm']:
            slpp = 'production.12TB'
        elif systems.values()[0]['maxCpu'] == 16:
            slpp = 'production.1TB'
        else:
            slpp = 'SmallTestVM'
    reload_target['slpp'] = slpp

    # Figure out if its enterprise or entry (its enterprise)
    dsserver = ''
    if t_props.has_key('dsserver.config'):
        dsserver = t_props['dsserver.config']
    else:
        print 'WARNING: %s is missing the property "dsserver.config", assuming the enterprise configuration...' % target
        dsserver = 'bluemix.medium'
    reload_target['dsserver'] = dsserver

    # If its MPP figure out replication factor (its 3)
    if reload_target['type'] == 'MPP' and t_props.has_key('replFactor'):
        reload_target['replFactor'] = t_props['replFactor']
    else:
        reload_target['replFactor'] = 3

    # Get Oracle compat mode (its false)
    if t_props.has_key('oracle.compat.mode') and t_props['oracle.compat.mode'] == 'true':
        reload_target['oracle'] = True
    else:
        reload_target['oracle'] = False

    reload_target['systems'] = systems.keys()

    # Get other properties that should be reused (portable IP)
    if t_props.has_key('portableIP'):
        reload_target['portableIP'] = t_props['portableIP']
    reload_target['saved_props'] = []
    for prop in t_props.items():
        if prop[0].startswith('NAS'):
            reload_target['saved_props'].append(prop)  # For NAS properties
        elif prop[0].startswith('dedicated'):
            reload_target['saved_props'].append(prop)  # For dedicated fix up process
        elif prop[0].startswith('Backup'):
            reload_target['saved_props'].append(prop)  # For supernode environments
        elif prop[0].startswith('Super'):
            reload_target['saved_props'].append(prop)  # For supernode environments
        elif prop[0].startswith('supernode.env'):
            reload_target['saved_props'].append(prop)  # For supernode environments

    # Show our work
    print 'Saving the following environment properties (in case of critical failure, please re-add these prior to redeployment...)'
    print json.dumps(reload_target['saved_props'], sort_keys=True, indent=2)

    if args.dryrun:
        print 'Just a dry run!  Aborting now that we have collected and displayed what would have been...'
        raise SystemExit(0)

    # Find the image we're reloading with
    reload_target['image'] = cli.get_app_prop(imagepropname[reload_target['type']][reload_target['vm']])

    ############################# RELOAD THE SYSTEMS ############################# 
    try:
        reload_systems(systems, reload_target, target)
    except SoftLayer.exceptions.SoftLayerAPIError:
        print 'API error reloading from image... maybe this is the US-Fed account?'
        reload_target['image'] = cli.get_app_prop(imagepropname[reload_target['type'] + '-fed'][reload_target['vm']])
        try:
            reload_systems(systems, reload_target, target)
        except SoftLayer.exceptions.SoftLayerAPIError:
            print 'ERROR: Unable to reload %s due to Softlayer exceptions' % target
            exit(1)

    ############################ CLEAN UP UCD ARTIFACTS ############################ 
    print 'Reload initiated.  Destroying UCD artifacts...'
    cli.delete_environment(target)

    ####################### WAIT FOR THE RELOADS TO COMPLETE ####################### 
    poolsize = len(systems)
    pool = ThreadPool(poolsize)
    pool.map(wait_reload, systems.values())
    pool.close()
    pool.join()

    ########################### RECAPTURE THE SYSTEM(S) ########################### 
    # Gather the new credentials and build reload json
    reloadjson = {}
    reloadjson['nodes'] = []
    for system in systems.values():
        node = {'sshid' : 'root'}
        if reload_target['vm']:
            node['sshpw'] = sl.get_cci_default_root_pw(system['id'])
        else:
            node['sshpw'] = sl.get_hw_default_root_pw(system['id'])
        node['ipaddress'] = system['primaryBackendIpAddress']
        if reload_target['type'] == 'SMP':
            node['role'] = 'reload'
        else:
            tokens = system['hostname'].split('-')
            node['role'] = tokens[-1]
        reloadjson['nodes'].append(node)

    # Delete the property if it exists and submit our updated json
    targetprop = '%sreload' % target
    cli.delete_app_prop(targetprop)
    cli.setapplicationprop(targetprop, json.dumps(reloadjson))

    # Submit the capture request
    processprops = {'name': target, 'blueprint': reload_target['blueprint'], 'pattern': targetprop}
    for x in range(5):
        try:
            cli.submit_and_wait('Toolserver: Capture Generic', parent, properties=processprops)
            break
        except SystemExit:
            print 'Capture failed...'
            if x == 4:
                print 'I give up.'
                raise SystemExit(1)
            else:
                print 'I will try again'

    # Delete the application property
    cli.delete_app_prop(targetprop)

    # Replace pertinant properties on the new target environment
    if reload_target.has_key('portableIP'):
        cli.setenvprop(target, 'portableIP', reload_target['portableIP'])
    for prop in reload_target['saved_props']:
        cli.setenvprop(target, prop[0], prop[1])

    pushprops = {
        'hostname' : hostname_base,
        #'portableIP' : reload_target['portableIP'] if reload_target.has_key('portableIP') else 'localhost', # remove me after portables goes live
        'sl-pp' : reload_target['slpp'],
        'dsserver.config' : reload_target['dsserver'],
        'oracle.compat.mode' : reload_target['oracle'],
        'replFactor' : reload_target['replFactor']
    }

    cli.submit_and_wait('Push properties to target env', parent, properties=pushprops)

    # Special case for supernode systems
    if 'SuperNodes' in reload_target['slpp'] and not reload_target['slpp'].endswith('-backup'):
        cli.submit_and_wait('Setup dashDB MPP Environment Properties', target)
        cli.submit_and_wait('Backup: Set Mounts on Super Node Servers', target)

    ########################### RELAUNCH DEPLOY ########################### 
    print 'Environment has been successfully reloaded, recaptured and reinitialized.'

    if args.snapshot is not None:
        cli.setenvprop(target, 'initial.deploy.snapshot', args.snapshot)
        if reload_target['type'] == 'Backup':
            requestid = cli.submit_process('Backup: Deploy System', target, snapshot=args.snapshot)
        else:
            requestid = cli.submit_process('Deploy dashDB (B)', target, snapshot=args.snapshot)
        print 'Redeployment snapshot of %s was given, you can monitor the progress of this process here:\nhttps://ucdeploy.swg-devops.com/#applicationProcessRequest/%s' % (args.snapshot, requestid)
    else:
        print 'No redeployment snapshot was given.  Your environment is blank, please run "Deploy dashDB (B)".  Goodbye.'

def wait_reload(system):
    ready = False
    while not (ready):
        print 'Waiting on Softlayer to finish reloading %s' % system['hostname']
        try:
            if system['vm']:
                ready = sl.mgr.wait_for_ready(system['id'], 60, delay=30, pending=True)
            else:
                ready = sl.wait_for_ready(system['id'], 60, delay=30)
        except Exception:
            print 'Oops... something went wrong checking Softlayer for %s, ill try again in a minute...' % system['hostname']
    print 'OS reload of %s complete!' % system['hostname']

def destroy_vms(systems, target):
    print 'Attempting to destroy %s and %s, standby...' % (', '.join(systems.keys()), target)
    for system in systems.values():
        if system['vm']:
            sl.destroycci(system['id'])
        else:
            print 'ERROR: I am unable to destroy bare metal systems at this time!'
            exit(1)

def get_slpp_type(slpp):
    if slpp.startswith('production.hadr'):
        return 'HA'
    elif slpp.endswith('-backup'):
        return 'Backup'
    elif slpp.startswith('MPP'):
        return 'MPP'
    else:
        return 'SMP'

def reload_systems(systems, reload_target, target):
    print 'Reloading %s and destroying %s, standby...' % (', '.join(systems.keys()), target)
    if DEBUG:
        print json.dumps(reload_target, indent=4, sort_keys=True)
    for system in systems.values():
        if system['vm']:
            sl.reload_server(sl.VIRTUAL, system['id'], reload_target['image'])
        else:
            sl.reload_server(sl.HARDWARE, system['id'], reload_target['image'])

if __name__ == "__main__":
    main(sys.argv[1:])

