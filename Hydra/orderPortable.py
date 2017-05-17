"""
Order Portable Ip script
"""
#!/usr/bin/python
import argparse,sys,json,os,SoftLayer
from SoftLayer import NetworkManager
from SoftLayer import utils
from cloudant.client import CouchDB
import json


if __name__ == '__main__':
    
