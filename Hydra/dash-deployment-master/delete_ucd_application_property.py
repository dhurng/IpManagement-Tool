#!/usr/bin/python
from ucd import cli
import argparse,sys

#########

def main(argv):
    parser = get_parser()
    args = parser.parse_args()

    if args.ucdtoken is not None:
        cli.set_token(args.ucdtoken)

    cli.delete_app_prop(args.property)

def get_parser():
    parser = argparse.ArgumentParser(description='Deletes application properties')
    parser.add_argument('property', help='The property to delete')
    parser.add_argument('-u','--ucdtoken', help='UCD access token')

    return parser

if __name__ == "__main__":
    main(sys.argv[1:])

