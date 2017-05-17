#!/usr/bin/python
# -*- coding: utf-8 -*-
"""A module for collecting functions that are useful to dashDB deployment across many different
tasks and not limited to one area (like ucd, softlayer or aws).

"""

import json,os,sys,argparse,time,datetime,socket,shutil
from subprocess import Popen, PIPE

#########

def set_net_device(device):
    """Sets a global variable for the network device to use for arping things

    Args:
        device (str): the device string like 'eth0'

    """
    global netdevice
    netdevice = device

#########

def is_portable_ip_available(portable):
    """Arps for an IP address and returns true if its "available" or false if
    it finds it (in use).  Not particularly useful, mostly left here as a reference as
    this will need to be run on a system in the VLAN in question and the toolservers are
    rarely in the same VLAN as the targets.

    Args:
        portable (str): an ip address

    Returns:
        bool: True if the ip address is available, false otherwise

    """
    try:
        run_command('arping -q -c 2 -w 3 -D -I %s %s' % (netdevice, portable))
        return True
    except SystemExit:
        return False

#########

def sshpass_do(ip, remotecommand, password=None):
    """Runs ssh commands but using the sshpass tool instead of regular ssh (for Softlayer systems). Using this over
    so that we don't introduce the requirement that we have to be able to manage ssh keys since that seems to be a
    contentious privilege in Softlayer land.

    Expects the os environment variable SSHPASS to be set with the root password for the system located at `ip`.

    Args:
        ip (str): the IP to connect to
        remotecommand (str): the command to execute, this will be wrapped in single quotes by the
            function so use double quotes if necessary.
        password (Optional[str]): Defaults to `None`.  If set will use an explicit password
            otherwise uses what is set in the os environment variable.

    """
    passwd = '-e' if password is None else '-p %s' % password
    command = "sshpass %s ssh -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no root@%s '%s'" % (passwd, ip, remotecommand)
    (stdout, stderr, rc) = run_command(command)
    if DEBUG:
        print(stdout)
    return stdout

#########

def scp(ip, localpath, password=None):
    """Runs sshpass scp to copy a file to a remote system.  Expects SSHPASS to be defined as an environment
    variable.

    Copys the file to the `/root` directory on the remote system

    Args:
        ip (str): the ip of the system to connect to
        localpath (str): a path to a file to copy
        password (Optional[str]): Defaults to `None`.  If set will use an explicit password
            otherwise uses what is set in the os environment variable.

    """
    passwd = '-e' if password is None else '-p %s' % password
    command = "sshpass %s scp -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no %s root@%s:/root" % (passwd, localpath, ip)
    (stdout, stderr, rc) = run_command(command)
    if DEBUG:
        print(stdout)


#########

def gen_id():
    """Generates a unique ID.

    Returns:
        str: a unique ID based off the timestamp.

    """
    ts = time.time()
    dt = datetime.datetime.fromtimestamp(ts).strftime('%Y%m%d_%H%M%S_%f')
    return dt

#########
# Thank you internet

def run_once(f):
    """A wrapper function that prevents another function from being called more than once.

    Args:
        f (function): the function to wrap

    """
    def wrapper(*args, **kwargs):
        if not wrapper.has_run:
            wrapper.has_run = True
            return f(*args, **kwargs)
    wrapper.has_run = False
    return wrapper

#########

def run_command(command):
    """Runs a command on the command line and returns the output.  If the return code is
    not 0 it raises SystemExit.

    Args:
        command (str): the command to run

    Returns:
        stdout (str): stdout from the output of the command
        stderr (str): stderr from the output of the command
        returnCode (int): the returnCode (this is stupid because its always going to be 0
            or its going to raise SystemExit)

    Raises:
        SystemExit: Right now the behaviour is to give up and die if anything non-zero happens and
            let the caller deal with it.  This isn't the most awesome behaviour but its worked so far.

    """
    if (command is not None):
        runThisCommand = command
    else:
        return None
    print "running command %s \n.." % command
    process = Popen(runThisCommand, shell=True, stdout=PIPE, stderr=PIPE)
    stdout, stderr = process.communicate()
    returnCode = process.wait()
    if (returnCode != 0) :
        print ">>> FAILURE running command <<<"
        print stderr
        sys.exit(returnCode)
    return (stdout, stderr, returnCode)


#########

@run_once
def set_runid(myid):
    """Sets a global runid variable for things like logging and work dirs.

    Args:
        myid (str): the id to use for the runid this run.

    """
    global runid
    runid = myid

#########

def parse_json(filename):
    """Parses a json file given the filename.

    Args:
        filename (str): name of the file to parse

    Returns:
        json: The parsed json

    """
    fd = open(filename,"r")
    json_data = fd.read()
    data = json.loads(json_data)
    return data

#########

def create_working_copy(filename):
    """Creates a working copy of a file or template.  Based on the global runid will copy a
    template file to the unique work directory.

    Args:
        filename (str): name of the file / template to make a working copy of

    Returns:
        str: absolute path to the working copy of the file

    """
    set_runid(gen_id())
    basename, extension = os.path.splitext(os.path.basename(filename))
    outfile = os.path.join(workdir, "%s-%s%s" % (basename, runid, extension))
    shutil.copyfile(filename, outfile)
    return os.path.realpath(outfile)

#########

def replace_token(token, replacement, filename):
    """Replaces a token in a file.

    Args:
        token (str): the token to replace
        replacement (str): the string to replace the token with
        filename (str): name of a file to replace the token in

    Returns:
        str: absolute path to the file that has the token replaced

    """
    tempfile = "/tmp/%s" % gen_id()
    with open(tempfile, "wt") as fout:
        with open(filename, "rt") as fin:
            for line in fin:
                fout.write(line.replace(token, replacement))
    shutil.move(tempfile, filename)
    return filename

#########

def remove_prefix(text, prefix):
    """Because this isn't a default python function for some reason...

    Args:
        text (str): the text to remove the prefix from...
        prefix (str): the prefix to remove

    Returns:
        str: removes the text minus the prefix or the text if it does not start with the prefix.

    """
    if text.startswith(prefix):
        return text[len(prefix):]
    return text

########################################

netdevice = 'eth1'
"""The network device name to use when doing network level tests
"""

DEBUG=False

scriptdir = os.path.dirname(os.path.realpath(__file__))
workdir = os.path.join(scriptdir, '..', 'work')
runid = ""
