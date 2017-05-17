#!/usr/bin/python
import json,os,sys,argparse
from ucd import cli

def main(argv):
    parser = get_parser()
    args = parser.parse_args()

    if args.token is not None:
        cli.set_token(args.token)

    resources = cli.get_env_base_resources(args.target)
    if len(resources) != 1:
        print 'ERROR: I don\'t know how to move this environment, I expect 1 base resource and it has %s' % len(resources)
        raise SystemExit(1)
    resource = resources[0]['path']
    newparent = '/CDS dashDB/%s' % args.environment

    # Make sure we're not trying to move to the same place

    res = json.loads(cli.udcli("getResource -resource '%s'" % resources[0]['id']))
    parentpath = res['parent']['path']
    if parentpath == newparent:
        print 'INFO: This environment is already right where it belongs!'
        raise SystemExit(0)

    # Do the move thing
    cli.move_resource(resource, newparent)

def get_parser():
    parser = argparse.ArgumentParser(description='Moves a dashDB environment\'s base resource to the correct parent base resource after it has completed provisioning.')
    parser.add_argument('-t', '--token', help='UCD Token')
    parser.add_argument('environment', help='The name of the deployment environment')
    parser.add_argument('target', help='The name of the environment to move')

    return parser

if __name__ == "__main__":

    main(sys.argv[1:])
