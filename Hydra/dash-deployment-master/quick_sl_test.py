#!/usr/bin/python
from softlayer import sl
import json,os,sys,argparse

def main(argv):
    parser = get_parser()
    args = parser.parse_args()

    if args.slid is not None:
        sl.set_creds(args.slid,args.slapi)

    account = sl.client.call('Account', 'getObject')
    print json.dumps(account, sort_keys=True, indent=2, separators=(',', ': '))

def get_parser():
    parser = argparse.ArgumentParser(description='A quick check to validate Softlayer tools deployment')
    parser.add_argument('-i','--slid', help='Softlayer ID')
    parser.add_argument('-k','--slapi', help='Softlayer API Key')

    return parser

if __name__ == "__main__":

    main(sys.argv[1:])

