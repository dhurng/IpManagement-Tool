#!/usr/bin/python
import json,os,sys,argparse
from ucd import cli
from softlayer import sl
import sort_environments as sort_e

DEBUG = False
ROLES = ['node', 'backup', 'pri', 'sby']

def main(argv):
    parser = get_parser()
    args = parser.parse_args()

    if args.env != 'CDS-Dev':
        print 'ERROR: Please rerun this from the CDS-Dev deployment environment'
        exit(1)

    global DEBUG
    if args.debug:
        print 'DEBUG output is ON'
    DEBUG = args.debug
    sl.DEBUG = args.debug
    cli.DEBUG = args.debug

    if args.slid is not None:
        sl.set_creds(args.slid, args.slapi)

    props = cli.get_component_env_props('dynamite-controller', args.env)
    all_systems = sl.get_systems_by_domain(props['domain'])
    all_envs = json.loads(cli.udcli("getEnvironmentsInApplication -application dashDB"))
    all_dev_envs = [env['name'] for env in all_envs if env['name'].startswith(tuple(sort_e.dev_rollups)) and not env['name'] in sort_e.dev_rollups and not env['name'].startswith(('AWS','Fyre'))]
    all_system_names = all_systems.keys()

    hung_systems = []
    orphaned_systems = []
    orphaned_environments = []
    matched_systems = []
    matched_environments = []

    if DEBUG:
        print 'Checking %s systems and %s environments for orphans and hung systems' % (len(all_system_names), len(all_dev_envs))
    for system_name in all_system_names:
        # Figure out what its doing
        system = all_systems[system_name]
        if system.has_key('activeTransaction'):
            if DEBUG:
                print 'Checking %s\'s active transaction...' % system_name
            # If its been longer than 2 hours consider it hung
            transaction = system['activeTransaction']
            if transaction.has_key('elapsedSeconds'):
                if transaction['elapsedSeconds'] > 7200:
                    hung_systems.append(system_name)
                    if DEBUG:
                        print '%s appears to be hung for %s seconds doing: "%s" Please see Softlayer for any open tickets.' % (system_name, transaction['elapsedSeconds'], transaction['transactionStatus']['friendlyName'])
                    continue
                elif DEBUG:
                    print '%s has an active transaction: %s, ongoing for %s, which is less than 2 hours so I am ignoring it for now...' % (system_name, transaction['transactionStatus']['friendlyName'], transaction['elapsedSeconds'])
            elif DEBUG:
                print '%s has an active transaction: %s, but no elapsed time, my guess is it is being decommissioned and I am ignoring this system.' % (system_name, transaction['transactionStatus']['friendlyName'])


        # System doesn't have an active transaction
        tokens = system_name.split('-')
        hostnamebase = system_name
        if tokens[-1].startswith(tuple(ROLES)):
            hostnamebase = '-'.join(tokens[0:-1])

        matched = False
        for env in all_dev_envs:
            if env.endswith(hostnamebase):
                matched_environments.append(env)
                matched_systems.append(system_name)
                matched = True
                if DEBUG:
                    print 'I found a match for %s in the all environment list' % system_name
                break
        if matched:
            continue

        # No match was found...
        if DEBUG:
            print 'I was unable to find a matching environment (and no active transaction on the following host), maybe its in the middle of being reloaded? or maybe its just orphaned...: %s' % system_name
        orphaned_systems.append(system_name)

    matched_environments = list(set(matched_environments))
    orphaned_environments = list(set(all_dev_envs) - set(matched_environments))

    formatstr = '{:<52} | {:16} | {:7}'
    print '\nI checked %s Softlayer systems and %s environments:' % (len(all_system_names), len(all_dev_envs))
    print '\nI found %s hung systems:\n' % len(hung_systems)
    for sys in hung_systems:
        sys_type = 'Virtual_Guest' if all_systems[sys]['vm'] else 'Hardware_Server'
        print formatstr.format(sys, sys_type, all_systems[sys]['datacenter']['name'])
    print '\nI found %s environments matching %s softlayer systems' % (len(matched_environments), len(matched_systems))
    print '\nI found %s orphaned UCD environments:\n' % len(orphaned_environments)
    for env in orphaned_environments:
        print env
    print '\nI found %s orphaned Softlayer systems:\n' % len(orphaned_systems)
    for sys in orphaned_systems:
        sys_type = 'Virtual_Guest' if all_systems[sys]['vm'] else 'Hardware_Server'
        print formatstr.format(sys, sys_type, all_systems[sys]['datacenter']['name'])


def get_parser():
    parser = argparse.ArgumentParser('Generates a report of abandoned systems in the cds dev account')
    parser.add_argument('-t', '--token', help='UCD Token')
    parser.add_argument('-d', '--debug', help='Turns on debug logging', default=False, action='store_true')
    parser.add_argument('env', help='The name of the deployment environment (must be "CDS-Dev")')
    parser.add_argument('-i', '--slid', help='Softlayer ID')
    parser.add_argument('-k', '--slapi', help='Softlayer API key')

    return parser

if __name__ == "__main__":

    main(sys.argv[1:])
