#!/usr/bin/python
from aws import provision as cli
import json,os,sys,argparse

def main(argv):
    parser = get_parser()
    args = parser.parse_args()

    if args.awsid is not None:
        cli.set_awsprofile(args.awsid,args.awssecret)

    cli.ec2('describe-instances')

def get_parser():
    parser = argparse.ArgumentParser(description='A quick check to validate deployment')
    parser.add_argument('-i','--awsid', help='AWS access key id')
    parser.add_argument('-s','--awssecret', help='AWS secret access key')

    return parser

if __name__ == "__main__":

    main(sys.argv[1:])
