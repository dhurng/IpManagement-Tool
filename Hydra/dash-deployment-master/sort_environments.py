#!/usr/bin/python
# -*- coding: utf-8 -*-
"""A quick and dirty script to sort all the dashDB environments, first by their type and then
by alphabetic order.  Uses multiple unsupported, undocumented UCD apis so this may or may not
continue to work in later UCD versions.

"""
from ucd import cli
from operator import itemgetter,attrgetter, methodcaller
import json,requests,os,itertools,argparse,sys

colors = {
    'red'           : '#D9182D',
    'orange'        : '#DD731C',
    'yellow'        : '#FFCF01',
    'green'         : '#17AF4B',
    'teal'          : '#007670',
    'blue'          : '#00B2EF',
    'darkred'       : '#A91024',
    'darkorange'    : '#B8461B',
    'darkyellow'    : '#FDB813',
    'darkgreen'     : '#008A52',
    'darkteal'      : '#006059',
    'darkblue'      : '#00648D',
    'blue2'         : '#008ABF',
    'lightpurple'   : '#AB1A86',
    'lightpink'     : '#F389AF',
    'taupe'         : '#838329',
    'gray'          : '#6D6E70',
    'gray2'         : '#83827F',
    'darkblue2'     : '#003F69',
    'purple'        : '#7F1C7D',
    'pink'          : '#EE3D96',
    'darktaupe'     : '#594F13',
    'darkgray'      : '#404041',
    'darkgray2'     : '#605F5C'
}
"""A mapping of human usable color names to color values
"""

types = {
    'special'       : -6,
    'guardium'      : -5,
    'toolservers'   : -4,
    'unstable'      : -3,
    'ops-test'      : -2,
    'dev'           : -1,
    'staging'       : 0,
    'staging-child' : 1,
    'ys'            : 2,
    'prod'          : 3,
    'aws'           : 4,
    'awsvpc'        : 5,
    'dedicated'     : 6,
    'usfed'         : 7,
    'hipaa'         : 8,
    'pcni'          : 9,
    'ys-child'      : 10,
    'prod-child'    : 11,
    'aws-child'     : 12,
    'vpc-child'     : 13,
    'ded-child'     : 14,
    'usfed-child'   : 15,
    'hipaa-child'   : 16,
    'pcni-child'    : 17,
    'dev-child'     : 18,
    'unknown'       : 19
}
"""A mapping of sorting types and their numerical sort order
"""

childtypes = [
    types['staging-child'],
    types['ys-child'],
    types['prod-child'],
    types['aws-child'],
    types['vpc-child'],
    types['ded-child'],
    types['usfed-child'],
    types['hipaa-child'],
    types['pcni-child'],
    types['dev-child'],
]
"""A list of types that are child types
"""

mappings = {
    types['staging']       : 'pink',
    types['staging-child'] : 'lightpink',
    types['ys']            : 'yellow',
    'rollups'              : 'darkorange',
    'satellites'           : 'orange',
    types['aws']           : 'darktaupe',
    types['awsvpc']        : 'darkblue2',
    types['dedicated']     : 'red',
    types['usfed']         : 'darkred',
    types['hipaa']         : 'darkgreen',
    types['pcni']          : 'purple',
    types['ys-child']      : 'darkyellow',
    'rollup-child'         : 'blue2',
    'sat-child'            : 'blue',
    types['aws-child']     : 'taupe',
    types['vpc-child']     : 'blue2',
    types['ded-child']     : 'teal',
    types['usfed-child']   : 'darkblue',
    types['hipaa-child']   : 'darkteal',
    types['pcni-child']    : 'lightpurple',
}
"""Maps a sort type to its color
"""

root_of_all_evil = ['YP', 'LYP', 'SYP']
"""The list of base, production rollup environments (YP, LYP and SYP)
"""

permutations = ['MPP', 'TXN', 'TXNHA']
"""Decorations that can appear on base production rollup environments and still be
base rollup environments
"""

cities = ['Montreal', 'Toronto', 'Washington', 'Paris', 'Milan', 'Amsterdam', 'Tokyo', 'Singapore',
          'HongKong', 'Frankfurt', 'Melbourne', 'Seoul', 'Chennai', 'Mexico' , 'SanJose', 'SaoPaulo', 'Dallas10']
"""A list of Softlayer 'cities' or data centers that compose create the possible permutations of
satellite rollup environments
"""

dev_rollups = ['AWS-DEV', 'TestBed', 'CDS-Dev', 'CDS-Dev-SJC', 'HIPAA-Dev', 'PCNI-Dev', 'Fyre-Dev', 'PCNI-Dev2']
"""Whitelist of development rollup environments
"""

unstable = ['AWS-Unstable', 'SL-Unstable']
"""Whitelist of unstable rollup environments
"""

guardium = ['Guardium Servers']
"""Whitelist of guardium server rollup environments
"""

ops_test = ['OpsTest', 'JT-Test', 'SRE']
"""Whitelist of ops-test rollup environments
"""

staging = ['Prod-Staging', 'Prod-Staging-MPP', 'Prod-Staging-TXN', 'Prod-Staging-TXNHA',
           'Prod-Staging-HIPAA', 'AWS-Staging']
"""Whitelist of prod-staging rollup environments
"""

ys1 = ['LYS1', 'YS1']
"""Whitelist of ys rollup environments
"""

special_envs = ['Relay-Cache', 'Build Imports Validator', 'APSM', 'APIS']
"""Whitelist of special environments
"""

toolservers = ['Development Toolservers', 'Production Toolservers']
"""Whitelist of toolserver rollup environments
"""

us_fed = ['US-Fed', 'US-Fed-Dal']
"""Whitelist of us-fed rollup environments
"""

aws_prod = ['AWS-USWest2', 'AWS-USEast1', 'AWS-APNE1']
"""Whitelist of aws-prod rollup environments
"""

aws_vpc = ['Valor', 'AWS-Valor']
"""Whitelist of aws-vpc rollup environments
"""

whitelist = ['Catalina-MPP', 'AFCU', 'IADB-WDC', 'IADB', 'AIMIA', 'Lennar', 'AIMIA-TOR', 'TAL',
        'Genpact-MPP', 'Genpact', 'Delhaize', 'Delhaize-MPP', 'Sysco-MPP', 'Talent_Insights',
             'Talent_Insights_2', 'NIANDC', 'SR3', 'ANZ', 'IBM-CIO', 'BCH-MPP', 'SCH',
             'IBM-CIO-TXNHA', 'Credit-Mutuel', 'TDBank', 'BCH-ENFIELD-MPP','Genpact-MPP-Enfield','Genpact-Enfield']
"""Whitelist of pcni rollup environments
"""

parent_satellites = []
"""Whiteslist of parent satellite rollup environments
"""

prod_parents = []
"""Whiteslist of production parent rollup environments
"""

def main(argv):
    global parent_satellites
    global prod_parents
    parser = get_parser()
    args = parser.parse_args()
    cli.DEBUG = args.debug
    if args.token is not None:
        cli.set_token(args.token)
    envs = json.loads(cli.udcli("getEnvironmentsInApplication -application dashDB"))
    names = [env['name'] for env in envs]

    a = [root_of_all_evil, permutations]
    rolls = list(itertools.product(*a))
    prod_parents = root_of_all_evil + ['-'.join(x) for x in rolls]

    a = [prod_parents, cities]
    rolls = list(itertools.product(*a))

    parent_satellites = ['-'.join(x) for x in rolls]

    for env in envs:
        if env['name'] in special_envs:
            env['type'] = types['special']
        elif env['name'] in toolservers:
            env['type'] = types['toolservers']
        elif env['name'] in guardium:
            env['type'] = types['guardium']
        elif env['name'] in unstable:
            env['type'] = types['unstable']
        elif env['name'] in ops_test:
            env['type'] = types['ops-test']
        elif env['name'] in dev_rollups:
            env['type'] = types['dev']
        elif env['name'] in staging:
            env['type'] = types['staging']
        elif env['name'] in ys1:
            env['type'] = types['ys']
        elif env['name'] in us_fed:
            env['type'] = types['usfed']
        elif env['name'] in prod_parents or env['name'] in parent_satellites:
            env['type'] = types['prod']
        elif env['name'] in aws_prod:
            env['type'] = types['aws']
        elif env['name'] in aws_vpc:
            env['type'] = types['awsvpc']
        elif env['name'].startswith(tuple(prod_parents + parent_satellites)):
            env['type'] = types['prod-child']
        elif env['name'].startswith(tuple(dev_rollups)):
            env['type'] = types['dev-child']
        elif env['name'].startswith(tuple(staging)):
            env['type'] = types['staging-child']
        elif env['name'].startswith(tuple(ys1)):
            env['type'] = types['ys-child']
        elif env['name'].startswith(tuple(us_fed)):
            env['type'] = types['usfed-child']
        elif env['name'].startswith(tuple(aws_prod)):
            env['type'] = types['aws-child']
        else:
            env['type'] = types['unknown']

    unknowns = [x for x in envs if x['type'] == types['unknown']]

    unknown_rollups = []
    for name in unknowns:
        if name['name'] in whitelist:
            unknown_rollups.append(name)
        elif not name['name'].startswith(tuple(whitelist)) and check_toolserver(name['name']):
            unknown_rollups.append(name)

    pcni = []
    hipaa = []
    dedicated = []
    for env in unknown_rollups:
        props = cli.get_component_env_props('dynamite-controller', env['name'])
        if props['hipaa'] == 'true':
            hipaa.append(env['name'])
            env['type'] = types['hipaa']
            print '%s is a HIPAA environment' % env['name']
        elif props['dedicated.env'] == 'true':
            dedicated.append(env['name'])
            env['type'] = types['dedicated']
            print '%s is a bluemix dedicated environment' % env['name']
        elif props['PCNI'] == 'true':
            pcni.append(env['name'])
            env['type'] = types['pcni']
            print '%s is a PCNI environment' % env['name']
        else:
            print 'I have no idea what %s is' % env['name']

    unknowns = [x for x in envs if x['type'] == types['unknown']]

    for env in unknowns:
        if env['name'].startswith(tuple(hipaa)):
            env['type'] = types['hipaa-child']
        elif env['name'].startswith(tuple(dedicated)):
            env['type'] = types['ded-child']
        elif env['name'].startswith(tuple(pcni)):
            env['type'] = types['pcni-child']

    envs.sort(key=itemgetter('type', 'name'))
    sorted_names = [x['name'] for x in envs]
    sorted_ids = [x['id'] for x in envs]

    base_url = 'https://ucdeploy.swg-devops.com/rest/deploy/application/7b0272e0-8cf4-4d54-9476-4e7bafac34c2/orderEnvironments'
    auth=('PasswordIsAuthToken', '{"token":"%s"}' % os.environ["DS_AUTH_TOKEN"])

    r = requests.put(base_url, data=json.dumps(sorted_ids), auth=auth)

    print 'Order environment request status code: %s' % r.status_code
    if r.status_code != 200:
        print r.json()

    ## Color the environments

    for env in envs:
        if env['type'] in childtypes:
            color_child_env(env)
        else:
            color_env(env)

def check_toolserver(env):
    """Helper function to check if an environment is a toolserver or not

    Args:
        env (str): the environment name

    Returns:
        bool: True if its a toolserver else, False

    """
    try:
        blueprint = cli.get_env_blueprint(env)
        if blueprint == 'toolserver':
            return True
        else:
            return False
    except SystemExit:
        return False

def color_child_env(env):
    if 'guardium' in env['name']:
        if env['color'] != colors['darkgray']:
            cli.color_environment(env['id'], colors['darkgray'])
    elif mappings.has_key(env['type']):
        if env['color'] != colors[mappings[env['type']]]:
            cli.color_environment(env['id'], colors[mappings[env['type']]])
    elif env['type'] == types['prod-child']:
        if env['name'].startswith(tuple(parent_satellites)):
            if env['color'] != colors[mappings['sat-child']]:
                cli.color_environment(env['id'], colors[mappings['sat-child']])
        elif env['name'].startswith(tuple(prod_parents)):
            if env['color'] != colors[mappings['rollup-child']]:
                cli.color_environment(env['id'], colors[mappings['rollup-child']])


def color_env(env):
    if mappings.has_key(env['type']):
        if env['color'] != colors[mappings[env['type']]]:
            cli.color_environment(env['id'], colors[mappings[env['type']]])
    elif env['type'] == types['prod']:
        if env['name'] in parent_satellites:
            if env['color'] != colors[mappings['satellites']]:
                cli.color_environment(env['id'], colors[mappings['satellites']])
        elif env['name'] in prod_parents:
            if env['color'] != colors[mappings['rollups']]:
                cli.color_environment(env['id'], colors[mappings['rollups']])


def get_parser():
    parser = argparse.ArgumentParser(description='A quick and dirty script for sorting and coloring dashDB UCD environments.  Relies on multiple unsupported, undocumented UCD APIs and may not work in subsequent UCD versions.')
    parser.add_argument('-d', '--debug', default=False, action='store_true', help='Turns on additional debug logging')
    parser.add_argument('--token', help='UCD Access Token')
    return parser

if __name__ == "__main__":
    main(sys.argv[1:])

