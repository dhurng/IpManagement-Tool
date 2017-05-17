# -*- coding: utf-8 -*-
"""A class whose sole purpose is checking dashDB portable IPs.
Used exclusively in the `portables.py` script.

"""
import sl
import os
import couchdb
from common import util
from ucd import cli

class IPChecker:
    """Represents a VM that checks Softlayer portable IPs for dashDB connectivity.

    Should only ever be instantiated using a with clause, never directly.

    Example:
        Use a with clause to instantiate IPChecker::

            with IPChecker(zone) as ipcheck:
                ipcheck.checkfirewallrules(environment, ip)

    Attributes:
        zone (json): deployment zone
        vsi (json): info on the Softlayer VM that is hosting the IP Checker
        sshpass (str): the root password for the IP Checker
        results (dict): the scanned IPs (keyed by 'ipaddress')
        DEBUG (bool): prints debug output or not (default = False)

    """
    def __init__(self, zone):
        """Should never be invoked directly (See notes on using the class in a `with` clause)

        Args:
            zone (json): the deployment zone this IP Checker is checking

        """
        self.zone = zone
        self.__setup__()

    def __enter__(self):
        """See __init__

        """
        return self

    def __setup__(self):
        """Does the initial VM setup.  Deploys a small test VM in the `zone`, pushes the IP Checker
        assets over to the VM and starts up a nginx server serving on the dashDB ports `8443`, `8787`,
        `33001`, `50000`, `50001`

        """
        print 'Deploying VM: dashdb-%s-portableip-checker' % self.zone['publicVLANid']
        self.vsi = sl.deploysmalltestvm('dashdb-%s-portableip-checker' % self.zone['publicVLANid'], self.zone['dataCenter'], self.zone['publicVLANid'], self.zone['privateVLANid'])
        self.sshpass = self.vsi['operatingSystem']['passwords'][0]['password']
        util.scp(self.vsi['primaryBackendIpAddress'], 'assets/ipchecker.tar.xz', self.sshpass)
        self.run_cmd('tar xJvf /root/ipchecker.tar.xz')
        self.run_cmd('/root/deploy.sh')
        self.results = {}
        self.DEBUG = False
        self.IPCheckProcess = 'Toolserver: Check Portable IP Firewall Rules'

    def __exit__(self, exc_type, exc_value, traceback):
        """Ensures the VM is destroyed when exiting a `with` clause.

        """
        sl.destroycci(self.vsi['id'])

    def checkifipinuse(self, ip):
        """Performs several checks:
            1. Checks DNS to see if its there.
            2. Checks to see if its reserved (skips futher checks if it is)
            3. ARPs to see if its in use

        Updates `results` with its findings and returns a boolean result on if the ip is in use or not.

        Args:
            ip (str): the ip to check

        Returns:
            bool: True if the IP is in use or False if it is available

        """
        host = sl.check_dns_for_ip(ip['ipAddress'])
        arp = self.run_cmd('arping -q -c 2 -w 3 -D -I eth1 %s' % ip['ipAddress'])
        ip['DNS'] = host
        rc = True
        if host is not None and arp == 0:
            if self.DEBUG:
                print '%s has a pre-existing DNS entry "%s" but does not appear to be in use, please clean this up and rescan to mark this as available before attempting to reuse' % (ip['ipAddress'], host)
            ip['scanResults'] = 'Unattached: Stale DNS: %s' % host
        if host is not None and arp == 1:
            if self.DEBUG:
                print '%s is in use as "%s"!' % (ip['ipAddress'], host)
            ip['scanResults'] = 'Attached: %s' % host
            ip['reserved'] = True
            ip['available'] = False
        if host is None and arp == 1:
            if self.DEBUG:
                print '%s is in use but I couldn\'t find a DNS entry for it, perhaps DNS is managed in a zone I am not currently tracking?.' % ip['ipAddress']
            ip['scanResults'] = 'Attached: Unknown'
            ip['reserved'] = True
            ip['available'] = False
        if host is None and arp == 0:
            if self.DEBUG:
                print '%s appears to be available' % ip['ipAddress']
            ip['scanResults'] = 'Tentatively Available'
            rc = False
        self.results[ip['ipAddress']] = ip
        return rc

    def attachportable(self, ip):
        """Attaches a portable IP to the VM.

        Args:
            ip (str): the portable IP to attach

        Returns:
            bool: True for success, else False

        """
        if self.run_cmd('/root/attachPortableIP.sh %s' % ip) == 0:
            return True
        else:
            print 'Failed to attach portable IP %s' % ip
            return False

    def detachportable(self):
        """Detaches the currently attached portable IP

        """
        self.run_cmd('ifconfig eth1:0 down')

    def checkfirewallrules(self, env, ip):
        """Checks an ip for open dashDB firewall rules.  Requires a UCD environment name to run
        the `Toolserver: Check Portable IP Firewall Rules` process against.  Updates `results`

        Args:
            env (str): the name of the environment to run the firewall check against (this is the
                parent deployment environment)
            ip (str): the ip to check

        """
        myref = self.results[ip['ipAddress']]
        if self.attachportable(ip['ipAddress']):
            props = {'ip': ip['ipAddress']}
            try:
                cli.submit_and_wait(self.IPCheckProcess, env, properties=props, delay=10)
                if self.DEBUG:
                    print '%s is "Available" and has access on dashDB ports, marking it as "Available"' % ip['ipAddress']
                myref['scanResults'] = 'Available'
                if not myref['reserved']:
                    myref['available'] = True
                else:
                    myref['scanResults'] = 'Reserved'
            except SystemExit:
                if self.DEBUG:
                    print '%s appears blocked on one or more dashDB ports, marking it as "Awaiting Firewall Rules"' % ip['ipAddress']
                myref['scanResults'] = 'Firewall Blocked'
                myref['available'] = False
            self.detachportable()

    def run_cmd(self, cmd):
        """Helper method to run a command on the IP Checker VM.

        Args:
            cmd (str): the command to run

        """
        try:
            util.sshpass_do(self.vsi['primaryBackendIpAddress'], cmd, self.sshpass)
            return 0
        except SystemExit:
            return 1

    def updateresults(self, portablesdb, vlanid):
        """Takes a reference to a couchdb (cloudant) database for portable IPs and updates it
        with `results`.

        Args:
            portablesdb (object): a reference to a `portableips` couchdb database (cloudant)
            vlandid (int): the ID of the vlan these ips belong to (to link back to the
                deployment zone in cloudant)

        """
        for ip in self.results.values():
            address = ip['ipAddress']
            if self.DEBUG:
                print 'Updating Softlayer notes on %s with %s' % (address, ip['scanResults'])
            sl.update_note_on_ip(ip['id'], ip['scanResults'])
            ip['note'] = ip['scanResults']
            if address in portablesdb:
                if self.DEBUG:
                    print 'Updating existing couchdb document for %s' % address
                portable = portablesdb[address]
                portable['reserved'] = ip['reserved']
                portable['available'] = ip['available']
                portable['lastScanResults'] = ip['scanResults']
                portable['DNS'] = ip['DNS']
                portablesdb[address] = portable
            else:
                if self.DEBUG:
                    print 'Creating new couchdb document for %s' % address
                portable = {
                    'SoftlayerID'      : ip['id'],
                    'ipAddress'        : address,
                    'reserved'         : ip['reserved'],
                    'available'        : ip['available'],
                    'lastScanResults'  : ip['scanResults'],
                    'deploymentzoneID' : str(vlanid),
                    'DNS'              : ip['DNS']
                }
                portablesdb[address] = portable
