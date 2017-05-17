#!/usr/bin/python
# -*- coding: utf-8 -*-
"""This module is a collection of functions used by some higher level command line scripts to
procure, tag and prepare aws instances for use in dashDB deployment.  It is very heavily geared
toward dashDB and some shortcuts were made in persuit of saving time that make it less than ideal
as a generic solution.

Basically any dashDB deployment script that would be interacting with AWS and requires some function
that may or may not be used again in another script gets dumped into here.  Currently this supports really
two different deployment types, dashDB mpp and guardium (used in dashDB).  Beyond that its not really tested
for anything else.  Its also dependent on having an AMI set up ahead of time in which you can run some sort
of root level scripting (either via ssh as root or ssh as sudoer where sudo is allowed without a tty).  Some
default amis may work with this, others may not.  For dashDB we had to create a custom CentOS 7 AMI so that
we could sudo without an attached tty before we could use this.

Example:
    On its own this module doesn't really **do** anything, its just a function library.
    For examples of provisioning aws using these functions see the procure_aws_* scripts in the root
    directory::

        $ python ../procure_aws_mpp.py -h
        $ python ../procure_aws_guardium.py -h

"""
import json,os,sys,argparse,time,datetime,socket,shutil
from common import util
from subprocess import Popen, PIPE

#########

def ec2(awscommand):
    """Wrapper around the aws cli.  Why we're using this over the api directly is a
    question we'll never know, maybe someday we'll get to it.  Every ec2 call should
    come through here so there is a common point to fix things (like adding the ability
    to set the region).

    Uses the util.run_command function so will indirectly raise SystemExit
    if the aws cli command fails.

    Args:
        awscommand (str): the command to feed to the aws cli, it will be wrapped in
            'aws ec2' so those should be ommitted.  Additionally the region should
            be figured out by the tooling so you shouldn't be passing --region to the
            function as it'll handle that on its own.

    Returns:
        str: stdout from 'aws ec2 [awscommand]'

    Raises:
        SystemExit: Indrectly will raise this if uncaught due to its reliance on
            util.run_command()

    """
    command = 'aws %s ec2 %s' % (region, awscommand)
    (stdout,stderr,rc) = util.run_command(command)
    return stdout

#########

def set_region(newregion):
    """Set the global variable for tracking which aws region we're in.
    Only useful if the defaul .aws/config is not set up correctly.

    Args:
        newregion (str): the aws region to use, i.e.: us-west-2

    """
    global region
    region = '--region %s' % newregion

#########

def release_elasticip(ip):
    """Releases an elastic ip.

    Args:
        ip (str): the elastic IP to release

    """
    address = json.loads(ec2('describe-addresses --public-ips %s' % ip))['Addresses'][0]
    ec2('disassociate-address --association-id %s' % address['AssociationId'])
    ec2('release-address --allocation-id %s' % address['AllocationId'])

#########

def get_keyname():
    """Gets the name of the aws key this system should be using (based on its hostname).

    Returns:
        str: basically its hostname with 'dash-deploy-' in front

    """
    (hostname,stderr,rc) = util.run_command("hostname")
    return 'dash-deploy-' + hostname.strip()

#########
# Thank you internet

def run_once(f):
    def wrapper(*args, **kwargs):
        if not wrapper.has_run:
            wrapper.has_run = True
            return f(*args, **kwargs)
    wrapper.has_run = False
    return wrapper

#########

@run_once
def set_domain(mydomain):
    """Sets the global variable for the domain.

    Args:
        mydomain (str): the domain name to use

    """
    global domain
    domain = mydomain

#########

@run_once
def set_awsprofile(awsid,awssecret):
    """Sets the aws access key id and secret access key into environment variables.  Run this
    once at the start of any script and then any api calls should work (assuming your key works).

    Args:
        awsid (str): the aws access key id to use for the duration of the process
        awssecret (str): the aws secret access key to use for the duration of the process

    """
    os.environ["AWS_ACCESS_KEY_ID"] = awsid
    os.environ["AWS_SECRET_ACCESS_KEY"] = awssecret

#########

@run_once
def validate_key():
    """Validates that we have a ssh key to use before we order anything

    """
    set_mykeyname()
    if not os.path.isfile(keyfile):
        print("Couldn't find %s" % keyfile)
        regenerate_keypair()
    if not aws_has_mykey():
        regenerate_keypair()

#########

def regenerate_keypair():
    """Deletes any existing keys that may exist by our name (locally and on aws) and recreates
    them.

    """
    print("Regenerating keypair")

    # remove any stale private keys
    keyfolder = scriptdir + '/keys'
    shutil.rmtree(keyfolder)
    os.makedirs(keyfolder)
    os.chmod(keyfolder, 0700)

    # remove any stale public keys
    try:
        ec2('delete-key-pair --key-name %s' % keyname)
    except SystemExit:
        print "Nothing to delete I guess..."

    # Soldier on 
    ec2("create-key-pair --key-name %s --query 'KeyMaterial' --output text > %s" % (keyname, keyfile))
    os.chmod(keyfile, 0400)

#########

def aws_has_mykey():
    """Checks aws for our ssh key.

    Returns:
        bool: True if it has it False if not

    """
    try:
        ec2('describe-key-pairs --key-name %s ' % keyname)
    except SystemExit:
        return False
    return True

#########

def set_sudoer(sudoer):
    """Sets the sudo user to connect to new nodes as when doing system setup.

    Args:
        sudoer (str): a user id to connect to new aws instances with when setup requires sudo

    """
    global globalsudoer
    globalsudoer = sudoer

#########

def set_mykeyname():
    """Overrides the default ssh key name that is based on the hostname if you want.

    """
    global mykey
    global keyname
    global keyfile
    keyname = get_keyname()
    mykey = keyname + '.pem'
    keyfile = '%s/keys/%s' % (scriptdir, mykey)

#########

def ssh_do(ip, remotecommand):
    """Runs a command remotely over ssh and using sudo.

    Args:
        ip (str): ip address of the system to ssh to.
        remotecommand (str): the command to run on the remote host

    """
    command = "ssh -i %s -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no %s@%s 'sudo %s'" % (keyfile, globalsudoer, ip, remotecommand)
    (stdout,stderr,rc) = util.run_command(command)
    print(stdout)
    print(stderr)

#########

def ssh_root(ip, remotecommand):
    """Runs a command remotely over ssh as root

    Args:
        ip (str): ip address of the system to ssh to.
        remotecommand (str): the command to run on the remote host

    """
    command = "ssh -i %s -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no root@%s '%s'" % (keyfile, ip, remotecommand)
    (stdout,stderr,rc) = util.run_command(command)
    print(stdout)
    print(stderr)

#########

def host_prep(public_ip, hostname, root_pass, nodes):
    """Runs a series of remote commands on a host to prepare it as an MPP host node.
    After running this the system should be ready for UCD capture.

    Args:
        public_ip (str): an ip (public or otherwise) that we can connect to on the host
        hostname (str): the hostname we should *set* on the node
        root_pass (str): the root password we should *set* on the node
        nodes (array): an array of dictionaries representing other nodes in the cluster.  Each
            node should have a value for 'private_ip' and 'hostname'

    """
    waitforip(public_ip)
    commandlist = [
           'sed -i "s/^PasswordAuthentication no/PasswordAuthentication yes/" /etc/ssh/sshd_config',
           'systemctl restart sshd',
           'hostnamectl set-hostname %s.%s' % (hostname, domain),
           'bash -c "echo preserve_hostname: true >> /etc/cloud/cloud.cfg"',
           'echo %s | sudo passwd root --stdin' % (root_pass)
]

    for key, node in nodes.items():
        commandlist.append('bash -c "echo %s %s.%s %s >> /etc/hosts"' % (node['private_ip'], node['hostname'], domain, node['hostname']))

    for command in commandlist:
        ssh_do(public_ip, command)
        time.sleep(2) # This is so dumb

#########

def rhel5_host_prep(ip, hostname, root_pass):
    """Runs host prep on a rhel 5 host for guardium setup.  Preparing a host for UCD capture on
    rhel 5 takes two steps as the system requires a reboot in between.

    Args:
        ip (str): the ip of the rhel 5 host we're preparing for UCD capture
        hostname (str): the hostname we should *set* on the node
        root_pass (str): the root password we should *set* on the node

    """
    waitforip(ip)
    commandlist = [
        'sed -i "s/^PasswordAuthentication no/PasswordAuthentication yes/" /etc/ssh/sshd_config',
        'sed -i "s/^PermitRootLogin without-password/PermitRootLogin yes/" /etc/ssh/sshd_config',
        'service sshd restart',
        'yum -y install java-1.7.0-openjdk',
        'echo "n\np\n1\n\n\np\nw\nq\n" | fdisk /dev/sda1 || true',
        'echo %s | passwd root --stdin' % (root_pass)
    ]

    for command in commandlist:
        ssh_root(ip, command)
        time.sleep(2) # yep, still dumb

#########

def rhel5_host_prep2(ip, hostname, root_pass):
    """Completes host preparation on rhel 5.  Completes the filesystem resize.

    Args:
        ip (str): the ip of the rhel 5 host we're preparing for UCD capture
        hostname (str): the hostname we should *set* on the node
        root_pass (str): the root password we should *set* on the node

    """
    waitforip(ip)
    commandlist = [
        'resize2fs /dev/sda1',
        'df -h'
        ]
    for command in commandlist:
        ssh_root(ip, command)
        time.sleep(2) # you know it

#########

def tag(tagname, instanceid, svcenv):
    """Tags a new aws instance with dashDB CDS tags to mark it as an MPP system.

    Args:
        tagname (str): the hostname for this system
        instanceid (str): the id of the aws instance to tag
        svcenv (str): "dev" or "prod"

    """
    ec2('create-tags --tags "Key=Name,Value=%s" --resources %s' % (tagname, instanceid))
    # hardcode those suckers... because that never comes back to bite us
    ec2('create-tags --tags "Key=provisioner,Value=cds_ucd_prov" --resources %s' % (instanceid))
    ec2('create-tags --tags "Key=cds:service,Value=dash" --resources %s' % (instanceid))
    ec2('create-tags --tags "Key=cds:svcplan,Value=mpp" --resources %s' % (instanceid))
    ec2('create-tags --tags "Key=cds:bmixenv,Value=yp" --resources %s' % (instanceid))
    ec2('create-tags --tags "Key=cds:svcenv,Value=%s" --resources %s' % (svcenv, instanceid))


#########

def allocate_elastic_ip():
    """Allocates an elastic IP

    Returns:
        allocation_id (str): the allocation id of the elastic ip
        elastic_ip (str): the ip address that was allocated

    """
    stdout = ec2('allocate-address --domain vpc')
    parsed_json = json.loads(stdout)
    #print(stdout)
    allocation_id = parsed_json['AllocationId']
    elastic_ip = parsed_json['PublicIp']
    return (allocation_id, elastic_ip)
#########

def set_elastic_ip(instance_id, wait=False):
    """Allocates and attaches an elastic IP to an instance.

    Args:
        instance_id (str): the aws instance to add an elastic ip to
        wait (Optional[bool]): Defaults to False.  If true will wait for the
            elastic IP to be available on the instance before returning.

    Returns:
        str: the elastic ip address that was attached to the instance

    """
    (allocation_id, elastic_ip) = allocate_elastic_ip()
    ec2('associate-address --instance-id %s --allocation-id %s' % (instance_id, allocation_id))
    #print(stdout)
    if wait:
        waitforip(elastic_ip)
    return elastic_ip

#########

def waituntilrunning(all_instances):
    """Wait for instances to be available.  This is really a lie, the instance
    may be available according to aws but if you attempted to ssh to it after this
    returns it would fail.

    Args:
        all_instances (str): a space separated string of instances to wait on.

    """
    stdout = ec2('wait instance-running --instance-ids %s'  % (all_instances))
    print stdout
    return stdout

#########

def waitforip(publicip):
    """Wait for instances doesn't really work, or rather, it works but you still can't
    connect to the systems.  This is an attempt to wait for the system to be really
    available.  Waits for a public ip to be reachable on the network.

    Args:
        publicip (str): the ip to wait for


    """
    for count in range (1, 20):  ## Never loops...
        print("Waiting for " + publicip + " to become available on the network...")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex((publicip,22))
        sock.close()
        if result == 0:
            break;  ## Hey, at least it works after waiting for like 40 seconds...
        time.sleep(10)

#########
def describebytag(tagprefix):
    """Queries aws for any instance matching `taprefix-*` and returns some selected values.  Mostly for setting
    up mpp nodes.

    Args:
        tagprefix (str): the base hostname to look for, will search for `tagprefix-*`

    Returns:
        json: the InstanceId, PublicDnsName, PrivateIpAddress, PublicIpAddress, StateReason of the
            node(s)

    """
    return lookupbytag("%s-*" % tagprefix)

#########
def terminatebytag(tag,releaseip = True):
    """Terminates a single aws instance by its `Name` tag.  If more than one system is found
    with that tag will print a message to standard out and return.

    Args:
        tag (str): the instance name to terminate
        releaseip (Optional[bool]): Defaults to true. Attempts to return the PublicIP of the
            system as if it were an elastic IP

    Returns:
        str: stdout from the terminate instance command

    """
    system = json.loads(lookupbytag(tag))
    if len(system) != 1:
        print("This tag is not unique!")
        return
    return terminatebyid(system[0][1],releaseip)

#########
def terminatebyid(instances,releaseip = True):
    """Terminates one or multiple instances by their instance ID.  Prior to terminating the instances will
    set their `Name` tag to empty and add an additional `deleted` tag with the original value of `Name`

    Args:
        instances (str): space separated list of instance to terminate
        releaseip (Optional[bool]): Defaults to true. Attempts to return the PublicIP of the
            system as if it were an elastic IP

    Returns:
        str: stdout from the terminate instance command

    """
    if releaseip:
        systems = json.loads(lookupbyids(instances))
        for system in systems:
            try:
                release_elasticip(system[4])
            except SystemExit:
                pass

    csvinst = instances.strip().replace(' ', ',')
    # Lets try to rename it so we don't block ourselves doing n+1 forever
    tags = json.loads(ec2('describe-tags --filters "Name=resource-id,Values=%s" "Name=key,Values=Name"' % csvinst))["Tags"]
    if len(tags) > 0:
        try:
            ec2('create-tags --tags "Key=deleted,Value=%s" --resources %s' % (tags[0]["Value"], instances))
            ec2('delete-tags --resources %s --tags Key=Name' % instances)
        except SystemExit:
            pass



    return ec2('terminate-instances --instance-ids %s' % instances)

#########
def lookupbytag(tag):
    """Queries aws for some instance information by its `Name` tag

    Args:
        tagprefix (str): the base hostname to look for, will search for `tagprefix-*`

    Returns:
        json: the InstanceId, PublicDnsName, PrivateIpAddress, PublicIpAddress, StateReason of the
            node(s)

    """
    stdout = ec2('--output json describe-instances --query "Reservations[].Instances[].[Tags[?Key==\`Name\`].Value, InstanceId, PublicDnsName, PrivateIpAddress, PublicIpAddress, StateReason]"  --filters "Name=tag:Name,Values=%s" '  % (tag))
    print(stdout)
    return stdout

#########
def lookupbyids(instances):
    """Performs the same lookup as lookupbytag but on instance IDs instead.

    Args:
        instances (str): space separated list of instances to query aws about

    Returns:
        json: the InstanceId, PublicDnsName, PrivateIpAddress, PublicIpAddress, StateReason of the
            node(s)

    """
    stdout = ec2('--output json describe-instances --query "Reservations[].Instances[].[Tags[?Key==\`Name\`].Value, InstanceId, PublicDnsName, PrivateIpAddress, PublicIpAddress, StateReason]"  --instance-id %s '  % (instances))
    print(stdout)
    return stdout

#########

def getsubnetidsbyvpc(vpcid):
    """Gets a list of subnet IDs from a VPC ID.

    Args:
        vpcid (str): the vpc id whos subnets ids to find

    Returns:
        array: list of strings of subnet IDs that belong to the `vpcid`

    """
    stdout = ec2('--output json describe-subnets --filter "Name=vpc-id,Values=%s"' % vpcid)
    subnets = json.loads(stdout)['Subnets']
    results = []
    for subnet in subnets:
        results.append(subnet['SubnetId'])
    return results

#########
def getsecuritygroupsbyvpc(vpcid):
    """Gets a list of security-groups from a VPC

    Args:
        vpcid (str): the vpc id whos security groups to find

    Returns:
        array: list of json entries describing the security groups

    """
    stdout = ec2('--output json describe-security-groups --filter "Name=vpc-id,Values=%s"' % vpcid)
    secgroups = json.loads(stdout)["SecurityGroups"]
    return secgroups

#########

@run_once
def create_working_template(profile, subnet, sg, ami):
    """Creates a completed working template from a given node configuration.
    Sets the global variable `workingtemplate` with the filename of the completed working copy.
    Once the function returns that file should be usale to order instances (presuming you've given it
    good values).

    Args:
        profile (str): filename to a node configuration template
        subnet (str): an aws subnet IDs
        sg (array): list of aws security group IDs
        ami (str): an aws ami ID

    """
    global workingtemplate
    validate_key()
    workingtemplate = util.create_working_copy(profile)
    util.replace_token("&KEYNAME&", keyname, workingtemplate)
    util.replace_token("&SUBNET&", subnet, workingtemplate)
    util.replace_token("&IMAGE&", ami, workingtemplate)
    util.replace_token("&SECURITYGROUP&", sg.replace(' ', '","'), workingtemplate)

#########

@run_once
def set_runid(myid):
    """Sets a global runid variable for things like logging and work directory if not using the default.
    By default uses `util.gen_id()`, but its nice to get the modules logging to the same filenames if you're
    using multiple modules.  Generally I set this to the UCD `${p:request.id}` that launched the entry point
    script.

    Args:
        myid (str): the id to set for the global runid

    """
    global runid
    runid = myid

#########

def get_role(role):
    """Gets the *arn* of a role by name.

    Args:
        role (str): the role name

    Returns:
        str: arn (amazon resource number?) of the given role

    """
    command = 'aws iam get-role --role-name %s' % (role)
    (stdout,stderr,rc) = util.run_command(command)
    role = json.loads(stdout)["Role"]
    return role

#########

def create_instance(tagname, profile, ami, subnet, sg, instanceprofile=None,svcenv='dev'):
    """Creates an aws instance and tags it.  This is entirely geared toward creating dashDB
    mpp systems and not a general purpose provisioning function. Shortcuts were taken.
    Mistakes were made. I think there may even be a filthy hack in there.  Caveat emptor if you're
    looking to use this for something other than set up dashDB instances.

    Args:
        tagname (str): the `Name` tag or hostname of the new instance
        profile (str): relative path filename of an aws instance configuration
        ami (str): the ami ID to provision with
        subnet (str): the subnet ID to provision with
        sg (array): a list of security group IDs to associate the new instance with
        instanceprofile (Optional[str]): Defaults to None. If present will launch the instance with the
            instanceprofile attached (so you can do ec2 commands without needing a key
        svcenv (Optional[str]): Defaults to 'dev'. The tag this instance should have for `cds:svcenv` to
            determine if its a development or production system.

    Returns:
        str: the instance id of the new instance

    """
    iamrole = ''
    if instanceprofile is not None:
        arn = get_role(instanceprofile)["Arn"]
        iamrole = '--iam-instance-profile Name=%s' % instanceprofile

    system = json.loads(lookupbytag(tagname))
    if len(system) != 0:
        print("A system with this tag appears to already exist!!!")
        sys.exit()
    responsefile = "%s/../logs/%s.%s" % (scriptdir, tagname, runid)
    create_working_template(profile, subnet, sg, ami)

    template = workingtemplate
    # Do the filthy hack
    node1template = workingtemplate + 'node1.json'
    if tagname.endswith("node1"):
        template = node1template
        with open(workingtemplate) as data_file:
            data = json.load(data_file)
            data["BlockDeviceMappings"] = data["BlockDeviceMappings"][:-2]
            with open(node1template, 'w') as node1_file:
                json.dump(data, node1_file)

    stdout = ec2("%s run-instances %s --cli-input-json file://%s > %s" % (region, iamrole, template, responsefile))
    print stdout
    parsed_json = util.parse_json(responsefile)
    instance_id = parsed_json['Instances'][0]['InstanceId']
    tag(tagname,instance_id,svcenv)
    return instance_id

#########

#########

mykey = ''
"""str: Name of the aws ssh key file this system uses. This is the filename only, not a path.
"""

keyname = ''
"""str: Name of the aws ssh key this system uses.  Really its just the hostname with `dashdb-deploy-`
in front of it.  Does not include the `.pem` extension, really just here because I'm that lazy.
"""

keyfile= ''
"""str: Relative path of the aws ssh key including its extension
"""

region = ''
"""str: The aws ec2 region where we're operating in, example: us-west-2
"""

globalsudoer = 'centos'
"""str: Username to use when doing ssh + sudo commands
"""

domain = 'dashdb.cdsdev.net'
"""str: The domainname to use when composing hostnames for new instances (tag + domain) = FQDN
"""

workingtemplate = ''
"""str: Path to the working template once a given process has selected a node configuration.
"""

order = {}
"""dict: Complex type that gets populated as nodes are ordered and configured (IP addresses are added,
hostnames are set, root passwords set, etc).
"""

capturejson = {}
"""dict: Similar to `order` but used specifically for UCD to capture the nodes once provisioning is complete
"""

scriptname = sys.argv[0]
scriptdir = os.path.dirname(os.path.realpath(__file__))
runid = util.gen_id()

