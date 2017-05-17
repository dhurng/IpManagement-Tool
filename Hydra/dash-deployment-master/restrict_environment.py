#!/usr/bin/python
import json,os,sys,argparse
from ucd import cli

def main(argv):
    parser = get_parser()
    args = parser.parse_args()

    cli.restrict_env(args.environment, args.type)

def get_parser():
    parser = argparse.ArgumentParser(description='Restricts an environment, resources and its agents to a particular team role')
    parser.add_argument('environment', help='The name of the environment to restrict')
    parser.add_argument('type', help="The type of environment role, 'Production Environment' or 'Prouction-HIPAA Environment' are valid examples")

    return parser

if __name__ == "__main__":

    main(sys.argv[1:])
