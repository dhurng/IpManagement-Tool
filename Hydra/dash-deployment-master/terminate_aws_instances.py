#!/usr/bin/python
from aws import provision
from ucd import cli
import argparse,sys

#########

def main(argv):
    parser = get_parser()
    args = parser.parse_args()

    exitcode = 0
    killkillkill = ""

    if args.awsid is not None:
        provision.set_awsprofile(args.awsid,args.awssecret)

    if args.environment:
        killkillkill = cli.get_env_prop(args.instances[0], 'ALL_INSTANCES')
    else:
        killkillkill = " ".join(args.instances)

    print "Destroying the following instances: %s ..." % killkillkill
    try:
        provision.terminatebyid(killkillkill,not args.preserveips)
    except SystemExit:
        exitcode = 1
        if args.environment:
            print "Failed to terminate any instances will clean up the environment..."

    if args.environment:
        cli.delete_environment(args.instances[0])
        numnodes = len(killkillkill.split())

    exit(exitcode)

def get_parser():
    parser = argparse.ArgumentParser(description='Destroyer of instances')
    parser.add_argument('instances',metavar='I', nargs='+', help='space separated list of instances to destroy')
    parser.add_argument('-e','--environment', action='store_true', default=False, help='Optionally give me a UCD environment to delete')
    parser.add_argument('-i','--awsid', help='AWS access key id')
    parser.add_argument('-s','--awssecret', help='AWS secret access key')
    parser.add_argument('-p','--preserveips', help='Preserve elastic IPs (does not automatically release them)',action='store_true', default=False)

    return parser
if __name__ == "__main__":
   main(sys.argv[1:])
