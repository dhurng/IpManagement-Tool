#!/usr/bin/python
from ucd import cli
import sys,argparse,json,os,time
from common import util
from aws import provision
from softlayer import sl

def main(argv):
    parser = get_parser()

    args = parser.parse_args()

    cli.set_token(args.token)
    provision.set_runid(args.callback)
    util.set_runid(args.callback)
    provision.set_awsprofile(args.id,args.key)
    cli.gen_workdir()

    # Do our setup
    args.func(args)

def set_overrides(args):
    #if args.domain is not None and args.domain != 'None':  ## redundant??
    #    cli.setcomponentenvprop(args.name, comp, 'domain', args.domain)
    if args.guardium is not None and args.guardium != 'None':
        cli.setcomponentenvprop(args.name, comp, 'guardium_server_ip', args.guardium)
    #if args.oauth2url is not None and args.oauth2url != 'None':  ## redundant??
    #    cli.setcomponentenvprop(args.name, comp, 'oauth2.discovery.url', args.oauth2url)
    #if args.swiftendpoint is not None and args.swiftendpoint != 'None':  ## redundant??
    #    cli.setcomponentenvprop(args.name, comp, 'swift.backup.endpoint', args.swiftendpoint)
    #if args.dc is not None and args.dc != 'None':  ## redundant??
    #    cli.setcomponentenvprop(args.name, comp, 'DC', args.dc)
    #if args.sslprocess is not None and args.sslprocess != 'None':  ## redundant??
    #    cli.setcomponentenvprop(args.name, comp, 'ssl.deploy.process', args.sslprocess)
    #if args.broker is not None and args.broker != 'None':  ## redundant??
    #    cli.setcomponentenvprop(args.name, comp, 'service.broker.endpoint', args.broker)
    #if args.brokerauth is not None and args.brokerauth != 'None':
    #    cli.setcomponentenvprop(args.name, comp, 'authorization.key', args.brokerauth)
    #if args.backuptime is not None and args.backuptime != 'None':  ## redudnant??
    #    cli.setcomponentenvprop(args.name, comp, 'BACKUP_TIME', args.backuptime)
    #if args.monregion is not None and args.monregion != 'None':  ## redudnant??
    #    cli.setcomponentenvprop(args.name, comp, 'monitoring.region', args.monregion)
    #if args.logregion is not None and args.logregion != 'None':  ## redundant??
    #    cli.setcomponentenvprop(args.name, comp, 'logging_region', args.logregion)
    if args.etcdpw is not None and args.etcdpw != 'None':
        cli.setcomponentenvprop(args.name, comp, 'etcd.password', args.etcdpw, True)
    if args.etcd1 is not None and args.etcd1 != 'None':
        cli.setcomponentenvprop(args.name, comp, 'etcd.endpoint1', args.etcd1)
    if args.etcd2 is not None and args.etcd2 != 'None':
        cli.setcomponentenvprop(args.name, comp, 'etcd.endpoint2', args.etcd2)

def dedicated(args):
    print 'Deploying new Softlayer Toolserver for dedicated environment', args.name
    name = args.name
    args.domain = args.domain.strip()

    # Order a new toolserver in the account
    processprops = {'new.env.name': name, 'softlayer.userid': args.id, 'softlayer.password': args.key, 'restricted.vlan': args.relay, 'domain': args.domain, 'bmixenv': 'cds:bmixenv:dedicated'}
    cli.submit_and_wait('Toolserver: Deploy New SoftLayer', args.parent, properties=processprops)

    # Restrict this to Production
    cli.restrict_env_to_prod(name)

    # Copy our parent controller's properties, as a starting point of reference
    cli.copy_component_environment_properties(comp, args.parent, args.name)
    # Copy our parent controller's secure properties
    if args.originaletcdpw is not None:
        cli.setcomponentenvprop(args.name, comp, 'etcd.password', args.originaletcdpw, True)

    # Pick up public bluemix settings for the DC (we'll delete the inappropriate ones)
    if args.dc is not None and args.dc != 'None':
        set_default_public_bluemix_settings(args.dc, args.name)

    # Set up dynamite-controller properties
    cli.setcomponentenvprop(args.name, comp, 'PROVIDER', 'SOFTLAYER')
    cli.setcomponentenvprop(args.name, comp, 'RestrictedVLAN', args.relay)
    cli.setcomponentenvprop(args.name, comp, 'env.type', 'YP')
    cli.setcomponentenvprop(args.name, comp, 'hipaa', 'false')
    cli.setcomponentenvprop(args.name, comp, 'PCNI', 'false')
    cli.setcomponentenvprop(args.name, comp, 'federal', 'false')
    cli.setcomponentenvprop(args.name, comp, 'dedicated.env', 'true')
    cli.setcomponentenvprop(args.name, comp, 'guardium_server_ip', 'None')
    cli.setcomponentenvprop(args.name, comp, 'service.broker.endpoint', '')
    cli.setcomponentenvprop(args.name, comp, 'authorization.key', '')
    # for dedicated we can construct the oauth2 url
    cli.setcomponentenvprop(args.name, comp, 'oauth2.discovery.url', 'https://api.%s/info' % args.domain)
    cli.setcomponentenvprop(args.name, comp, 'domain', args.domain)

    # Save our SL credentials
    cli.setcomponentenvprop(args.name, comp, 'sl-uid', args.id)
    cli.setcomponentenvprop(args.name, comp, 'sl-api-pw', args.key, secure=True)

    # Old school overrides for dedicated
    if args.sslprocess is not None and args.sslprocess != 'None':
        cli.setcomponentenvprop(args.name, comp, 'ssl.deploy.process', args.sslprocess)
    else:
        cli.setcomponentenvprop(args.name, comp, 'ssl.deploy.process', 'None')
    if args.broker is not None and args.broker != 'None':
        cli.setcomponentenvprop(args.name, comp, 'service.broker.endpoint', args.broker)
    else:
        cli.setcomponentenvprop(args.name, comp, 'service.broker.endpoint', 'None')
    if args.brokerauth is not None and args.brokerauth != 'None':
        cli.setcomponentenvprop(args.name, comp, 'authorization.key', args.brokerauth)
    else:
        cli.setcomponentenvprop(args.name, comp, 'authorization.key', 'None')

    # This is a production environment, and we have to set this twice...
    cli.setenvprop(args.name, 'env.type', 'YP')

    # Ask and set the override current.kernel
    currentkernel = cli.get_app_prop('current.kernel.centos7')
    cli.setenvprop(args.name, 'current.kernel', currentkernel)

    agents = cli.get_agents_from_environment(name)
    for agent in agents:
        cli.set_agent_prop(agent, 'PROVIDER', 'SOFTLAYER')
        cli.set_agent_prop(agent, 'sl-uid', args.id)
        cli.set_agent_prop(agent, 'sl-api-pw', args.key, secure=True)
        private_ip = cli.get_agent_prop(agent, 'ip')
        cli.setcomponentenvprop(args.name, comp, 'toolserver.ip', private_ip)

    # Set IEM/SSO properties
    cli.setenvprop(args.name, 'iem.sso.customer', name)
    cli.setenvprop(args.name, 'iem.sso.dc', args.dc)
    cli.setenvprop(args.name, 'iem.sso.plan', '-')
    cli.setenvprop(args.name, 'iem.sso.network', 'DEDICATED')
    cli.setenvprop(args.name, 'iem.sso.region', 'us-south')

    # Run Initial Setup and the Toolserver Install
    cli.submit_and_wait('Toolserver: Setup New', args.name)
    # Finally, run the Bluemix Dedicated Bootstrap (which reruns Initial Setup... Ugly, I know..)
    cli.submit_and_wait('Toolserver: Bootstrap Bluemix Dedicated', args.name)
    # Fin

def rollup(args):
    name = args.name
    print 'Generating rollup deployment environment for', args.name
    prod = args.production is not None and args.production == "true"

    # Check to see if we're trying to make a rollup from a dedicated environment
    parent_props = cli.get_component_env_props('dynamite-controller', args.parent)
    if parent_props['dedicated.env']:
        agentid = cli.get_toolserver_agentid(args.parent)
    else:
        agentid = None
    # Create a new environment from our parent
    agent_res = new_env_setup(args, production=prod, agentid=agentid)
    cli.udcli("createResource %s" % agent_res)

    if args.parentenv != 'None':
        # Add the new environment to the parent's base resources (for updates)
        cli.add_base_resource(args.parent, '/CDS dashDB/%s' % name) # Beware of magic strings

def new_env_setup(args, production=True, agentid=None):
    name = args.name

    # Create environment from template
    create_env = cli.replace_tokens("&NAME&", name, "DeploymentEnvironment.json")
    cli.udcli("provisionEnvironment %s" % create_env)

    # Delete the agent template and add the toolserver agent
    cli.udcli("deleteAgent -agent dashDB-%s-Toolserver" % name)
    cli.replace_tokens("&NAME&", name, "NewAgentResource.json")
    if production:
        if agentid == None:
            agentid = cli.udcli("getApplicationProperty -application dashDB -name bluemix.services.toolserver.id").strip()
        # Do this BEFORE we add the dev or prod default toolserver agent or we could potentially mess up the 
        # Teams for those agents (those agents are special).  But also don't add the agent yet in case we're
        # Not just production but HIPAA and doing this whole thing again (not ideal)
        cli.restrict_env_to_prod(name)
    else:
        if agentid == None:
            agentid = cli.udcli("getApplicationProperty -application dashDB -name cdsdev.toolserver.id").strip()
    agent_res = cli.replace_tokens("&AGENTID&", agentid, "NewAgentResource.json")

    # Pick up our parent's properties by default
    cli.copy_component_environment_properties(comp, args.parent, name)
    cli.copy_component_environment_properties('Cdsmon:base', args.parent, args.name)
    cli.copy_component_environment_properties('Cdsmon:uptime_check', args.parent, args.name)
    cli.copy_component_environment_properties('cdsmon:setup_UI_check_dashDB', args.parent, args.name)
    cli.copy_component_environment_properties('CDS Logging', args.parent, args.name)

    # Copy our parent controller's secure properties
    if args.originaletcdpw is not None:
        cli.setcomponentenvprop(args.name, comp, 'etcd.password', args.originaletcdpw, True)

    # Set the relay
    cli.setcomponentenvprop(name, comp, 'RestrictedVLAN', args.relay)

    # Store the SL api key 
    cli.setcomponentenvprop(name, comp, 'sl-api-pw', args.key, True)

    # If we're given a DC, make sure we're setting the right defaults for that DC
    if args.dc is not None and args.dc != 'None':
        set_default_public_bluemix_settings(args.dc, args.name)

    # Set any overrides we were given from the command line
    set_overrides(args)

    # Set explicit flags 
    cli.setcomponentenvprop(name, comp, 'PCNI', 'false')
    cli.setcomponentenvprop(name, comp, 'hipaa', 'false')
    cli.setcomponentenvprop(name, comp, 'federal', 'false')
    #cli.setcomponentenvprop(name, comp, 'dedicated.env', 'false') # Maybe we dont want to do this...
    # In case we're creating a rollup of a dedicated environment
    dedicated_props = ['dedicated.iem', 'dedicated.iem.hostname', 'dedicated.qradar']
    for propname in dedicated_props:
        try:
            propvalue = cli.get_env_prop(args.parent, propname)
            cli.setenvprop(name, propname, propvalue)
        except SystemExit:
            pass

    return agent_res

def pcni(args):
    print 'Generating PCNI deployment environment for', args.name
    name = args.name

    # Create a new environment from our parent
    agent_res = new_env_setup(args)
    cli.udcli("createResource %s" % agent_res)

    # Add the new environment to the parent's base resources (for updates)
    cli.add_base_resource(args.parent, '/CDS dashDB/%s' % name) # Magic string!!!!

    # Set PCNI flag 
    cli.setcomponentenvprop(name, comp, 'PCNI', 'true')

    # PCNI environments get their own dedicated guardium servers, don't use our parents
    cli.setcomponentenvprop(name, comp, 'guardium_server_ip', 'None')
    # Fin

def enfield(args):
    print 'Generating Enfield deployment environment for', args.name
    name = args.name
    agentid = cli.udcli("getApplicationProperty -application dashDB -name apsm.toolserver.id").strip()

    # Create a new environment from our parent
    oldparent = args.parent
    args.parent = 'APIS' ## WHAT?! WHO?! HOW?!
    agent_res = new_env_setup(args, agentid=agentid)

    # If this is a HIPAA environment do additional restrictions
    if args.hipaa:
        cli.restrict_env(name, 'Production-HIPAA Environment')
        cli.setcomponentenvprop(name, comp, 'hipaa', 'true')

    cli.udcli("createResource %s" % agent_res)

    # Add the new environment to the parent's base resources (for updates)
    # Figure out how to deal with this
    cli.add_base_resource(oldparent, '/CDS dashDB/%s' % name) # Magic string!!!!

    # Set PCNI flag 
    cli.setcomponentenvprop(name, comp, 'PCNI', 'true')

    # PCNI environments get their own dedicated guardium servers, don't use our parents
    cli.setcomponentenvprop(name, comp, 'guardium_server_ip', 'None')
	#Fin

def hipaa(args):
    print 'Generating HIPAA deployment environment for', args.name
    name = args.name

    # Create a new environment from our parent
    agent_res = new_env_setup(args)
    cli.restrict_env(name, 'Production-HIPAA Environment')
    cli.udcli("createResource %s" % agent_res)

    # Add the new environment to the parent's base resources (for updates)
    cli.add_base_resource(args.parent, '/CDS dashDB/%s' % name) # Magic string!!!!

    # Set PCNI and hipaa flags
    cli.setcomponentenvprop(name, comp, 'PCNI', 'true')
    cli.setcomponentenvprop(name, comp, 'hipaa', 'true')

    # hipaa environments get their own dedicated guardium servers, don't use our parents
    cli.setcomponentenvprop(name, comp, 'guardium_server_ip', 'None')
    # Fin

def awsprod(args):
    print "Creating new production AWS deployment environment for ", args.region
    name = args.name
    provision.set_region(args.region)
    tagname = 'dashdb-%s-toolserver' % args.name
    instance_id = provision.create_instance(tagname, 'aws/templates/micro2.json' , args.ami, args.subnet,
                                            args.securitygroup[0], instanceprofile='am_dashdb_role', svcenv='production_deploy')
    print "==== tagname: %s, instance_id : %s \n" % (tagname, instance_id)
    order[instance_id] = {}
    nodeinfo = json.loads(provision.lookupbytag(tagname))[0]
    private_ip = nodeinfo[3]
    statereason = nodeinfo[5]
    if private_ip is None:
        print "Looks like your instances failed to come up, bummer"
        print "Clean up your resources and try again or request a limit increase on the account"
        print 'ALL_INSTANCES=', json.dumps(statereason)
        raise SystemExit(1)

    order[instance_id]['private_ip'] = private_ip
    order[instance_id]['hostname'] = tagname
    (stdout, stder, rc) = util.run_command("date +%s | sha256sum | base64 | head -c 24 ; echo")
    root_pw = stdout.strip()
    order[instance_id]['root_pw'] = root_pw
    order[instance_id]['nodeid'] = 1
    print "waiting for instance %s to be up \n" % instance_id

    provision.waituntilrunning(instance_id)
    print("Taking a nap...")
    time.sleep(120) # This is so dumb
    # Give it a public IP
    host_ip = provision.set_elastic_ip(instance_id)
    order[instance_id]['public_ip'] = host_ip
    # For testing, basically, port 22 usually wont even be open here
    if args.public:
        provision.host_prep(host_ip, order[instance_id]['hostname'], order[instance_id]['root_pw'], order)
    else:
        provision.host_prep(order[instance_id]['private_ip'], order[instance_id]['hostname'], order[instance_id]['root_pw'], order)
    ucdnodes.append({"sshid" : "root", "sshpw" : order[instance_id]['root_pw'], "role" : "toolserver", "ipaddress" : order[instance_id]['private_ip']})
    provision.describebytag(tagname)
    print(json.dumps(order))
    capturejson['nodes'] = ucdnodes
    dumpedcapturejson = json.dumps(capturejson)
    print(dumpedcapturejson)
    cli.setapplicationprop(args.callback, dumpedcapturejson)
    print 'ALL_INSTANCES=%s' % instance_id.strip()
    print 'ELASTIC_IPS=%s' % host_ip.strip()
    print 'NODE_CFG=%s' % order
    # And we have a system...

    # Lets ask UCD to capture the system now
    processprops = {'name': args.name, 'relay': args.relay, 'callback': args.callback }
    cli.submit_and_wait('Toolserver: Capture AWS', args.parent, properties=processprops)

    # Restrict this environment to production use
    cli.restrict_env_to_prod(args.name)

    # Set some AWS specific interesting things
    cli.setenvprop(args.name, 'NODE_CFG', json.dumps(order))
    cli.setenvprop(args.name, 'PublicIP', host_ip.strip())

    # Copy our parent's controller properties, as a starting point of reference
    cli.copy_component_environment_properties(comp, args.parent, args.name)

    # Copy our parent's SL credentials so we can create DNS records
    processprops = {'target': args.name }
    cli.submit_and_wait('Toolserver: Copy SL Credentials', args.parent, properties=processprops)

    # Set up dynamite-controller properties
    cli.setcomponentenvprop(args.name, comp, 'aws.subnet', args.subnet)
    cli.setcomponentenvprop(args.name, comp, 'aws.security.group', ' '.join(args.securitygroup))
    cli.setcomponentenvprop(args.name, comp, 'PROVIDER', 'AWS')
    cli.setcomponentenvprop(args.name, comp, 'RestrictedVLAN', args.relay)
    cli.setcomponentenvprop(args.name, comp, 'env.type', 'YP')
    cli.setcomponentenvprop(args.name, comp, 'aws.region', args.region)
    cli.setcomponentenvprop(args.name, comp, 'monitoring.region', 'aws-%s' % args.region)
    cli.setcomponentenvprop(args.name, comp, 'aws.dash.ami', args.ami)
    cli.setcomponentenvprop(args.name, comp, 'aws.guardium.ami', args.guardami)
    cli.setcomponentenvprop(args.name, comp, 'toolserver.ip', order[instance_id]['private_ip'])
    cli.setcomponentenvprop(args.name, comp, 'hipaa', 'false')
    cli.setcomponentenvprop(args.name, comp, 'PCNI', 'false')
    cli.setcomponentenvprop(args.name, comp, 'federal', 'false')
    cli.setcomponentenvprop(args.name, comp, 'dedicated.env', 'false')
    cli.setcomponentenvprop(args.name, comp, 'guardium_server_ip', 'None')

    # Set these as secure properties so tricksy hobitses can't use them
    cli.setenvprop(args.name, 'aws.access.key.id', args.id, secure=True)
    cli.setenvprop(args.name, 'aws.secret.access.key', args.key, secure=True)

    # This is a production environment, and we have to set this twice...
    cli.setenvprop(args.name, 'env.type', 'YP')

    # Set IEM/SSO properties so that they'll work in AWS (assuming the tunnel exists)
    cli.setenvprop(args.name, 'iem.sso.customer', '-')
    cli.setenvprop(args.name, 'iem.sso.dc', args.region)
    cli.setenvprop(args.name, 'iem.sso.plan', '-')
    cli.setenvprop(args.name, 'iem.sso.network', 'CPSM')
    cli.setenvprop(args.name, 'iem.sso.region', 'us-south')

    # Ask and set the override current.kernel
    currentkernel = cli.get_app_prop('current.kernel.centos7')
    cli.setenvprop(args.name, 'current.kernel', currentkernel)

    agents = cli.get_agents_from_environment(name)
    for agent in agents:
        cli.set_agent_prop(agent, 'PROVIDER', 'AWS')

    # Get the public bluemix settings for logging / monitoring / SSL / etc
    set_default_public_bluemix_settings(args.datacenter, args.name)

    # Finally, run Initial Setup and the Toolserver Install
    cli.submit_and_wait('Toolserver: Setup New', args.name)
    # Fin

def awsvpc(args):
    name = args.name
    comp = 'dynamite-controller'
    sgs = provision.getsecuritygroupsbyvpc(args.vpcid)
    subnets = provision.getsubnetidsbyvpc(args.vpcid)

    if len(subnets) == 0:
        print 'ERROR: This VPC does not have any subnets defined!'
        raise SystemExit(1)
    if len(sgs) == 0:
        print 'ERROR: This VPC does not have any security groups defined!'
        raise SystemExit(1)

    # Just picking one...
    subnet = subnets[0]
    secuitygroup = None
    rules = 0
    for sg in sgs:
        if len(sg["IpPermissions"][0]["IpRanges"]) > rules:
            rules = len(sg["IpPermissions"][0]["IpRanges"])
            securitygroup = sg['GroupId']
            # Just going for the one with the most rules as the IBM access SG for now...

    # Create agent_res from our parent _not_ the default public agent
    agentid = cli.get_toolserver_agentid(args.parent)
    agent_res = new_env_setup(args, agentid=agentid)
    cli.udcli("createResource %s" % agent_res)

    # Set our specific properties
    cli.setcomponentenvprop(args.name, comp, 'aws.subnet', subnet)
    cli.setcomponentenvprop(args.name, comp, 'aws.security.group', securitygroup)

    # Copy our parent's SL credentials so we can create DNS records
    processprops = {'target': args.name }
    cli.submit_and_wait('Toolserver: Copy SL Credentials', args.parent, properties=processprops)

    # Set these as secure properties so tricksy hobitses can't use them
    cli.setenvprop(args.name, 'aws.access.key.id', args.id, secure=True)
    cli.setenvprop(args.name, 'aws.secret.access.key', args.key, secure=True)

    # This is a production environment, and we have to set this twice...
    cli.setenvprop(args.name, 'env.type', 'YP')

    # Ask and set the override current.kernel
    currentkernel = cli.get_app_prop('current.kernel.centos7')
    cli.setenvprop(args.name, 'current.kernel', currentkernel)

    # Private VPC environments get their own dedicated guardium servers, don't use our parents
    cli.setcomponentenvprop(name, comp, 'guardium_server_ip', 'None')

    # Add the new environment to the parent's base resources (for updates)
    cli.add_base_resource(args.parent, '/CDS dashDB/%s' % name) # Beware of magic strings
    # Fin

def get_parser():
    parser = argparse.ArgumentParser(description='A helper script to provision deployment environments in UCD')
    parser.add_argument('name', help='Name of the deployment environment.  No spaces')
    parser.add_argument('parent', help='Name of the parent deployment environment (where this is being run from).')

    parser.add_argument('id', help='Provisioning ID (Softlayer ID or AWS Access Key) for new Deployment Environment')
    parser.add_argument('key', help='Provisioning Key (Softlayer API Key or AWS Secret Access Key) for new Deployment Environment')
    parser.add_argument('token', help='UCD Access Token')
    parser.add_argument('relay', help='UCD Relay Zone')
    parser.add_argument('callback', help='Process ID for logging purposes')

    # "Override" properties, since UCD will always give them will check them at runtime for the string "None"
    # The original etcdpw so we can copy it (overrides would still apply)
    parser.add_argument('--originaletcdpw', help='Parent environment\'s etcdpw (can still be overriden by --etcdpw)', default='None')
    parser.add_argument('-d', '--domain', help='Domain name')
    parser.add_argument('--oauth2url', help='OAUTH2 Discovery URL for bluemix SSO')
    parser.add_argument('--swiftendpoint', help='Swift backup endpoint (for Softlayer backups)')
    parser.add_argument('--dc', help='Softlayer DataCenter.  For AWS use the closest geographical analog')
    parser.add_argument('--sslprocess', help='SSL deploy process (if different from parent copying from)')
    parser.add_argument('-b', '--broker', help='Service broker endpoint (should end in /providers)')
    parser.add_argument('-z', '--brokerauth', help='Service broker authroizeation Key')
    parser.add_argument('--guardium', help='Guardium Server IP')
    parser.add_argument('--monregion', help='Monitoring Region')
    parser.add_argument('--logregion', help='Logging Region')
    parser.add_argument('--backuptime', help='Backup time (for Softlayer)')
    parser.add_argument('--etcdpw', help='etcd password for HA Txn plans')
    parser.add_argument('--etcd1', help='etcd endpoint1 for HA Txn plans')
    parser.add_argument('--etcd2', help='etcd endpoint2 for HA Txn plans')

    subparsers = parser.add_subparsers(title='Type', description='New environment type', help='Newly created deployment environment type')

    parser_dedicated = subparsers.add_parser('dedicated', help='New Bluemix Dedicated environment')
    parser_pcni = subparsers.add_parser('pcni', help='New PCNI environment')
    parser_rollup = subparsers.add_parser('rollup', help='New Rollup environment')
    parser_hipaa = subparsers.add_parser('hipaa', help='New HIPAA ready environment')
    parser_enfield = subparsers.add_parser('enfield', help='New enfield environment (private deployment, like PCNI, but in the APIS account)')
    parser_usfed = subparsers.add_parser('us-fed', help='New US-Fed environment')
    parser_awsprod = subparsers.add_parser('aws-prod', help='New AWS production environment')
    parser_awsvpc = subparsers.add_parser('aws-vpc', help='New AWS private VPC environment')

    parser_awsprod.add_argument('ami', help='ID of the dashDB base AMI in the new availability zone')
    parser_awsprod.add_argument('guardami', help='ID of the guardium base AMI in the new availability zone')
    parser_awsprod.add_argument('region', help='Where is this new deployment environment')
    parser_awsprod.add_argument('subnet', help='Default subnet for new deployment environment')
    parser_awsprod.add_argument('securitygroup', nargs='+', help='The VPCs security groups.  Be sure to list the APSM security group first.')
    parser_awsprod.add_argument('-p', '--public', help='Use the public IP for prepping the host (testing purposes only)',
                                action='store_true', default=False)
    parser_awsprod.set_defaults(func=awsprod)

    parser_enfield.add_argument('--hipaa', default=False, action='store_true', help='For HIPAA enfield deployment environments')
    parser_enfield.set_defaults(func=enfield)

    parser_awsvpc.set_defaults(func=awsvpc)
    parser_awsvpc.add_argument('vpcid', help='The vpc id of the new private VPC deployment environment')

    parser_pcni.set_defaults(func=pcni)

    parser_rollup.add_argument('--production', help='"true" if a production rollup environment, otherwise will be considered not production', required=True)
    parser_rollup.add_argument('--parentenv', help='If this rollup environment is a sub-rollup parentenv=parent, otherwise parentenv should be set to "None"', required=True)
    parser_rollup.set_defaults(func=rollup)

    parser_hipaa.set_defaults(func=hipaa)

    parser_dedicated.set_defaults(func=dedicated)

    return parser

def set_default_public_bluemix_settings(datacenter, target):
    """Sets certain `dynamite-controller` properties to the appropriate values for the given
    SoftLayer datacenter for the environment to function in public bluemix (regardless of what
    account the dash system actually lives in).

    The properties this function sets are:
        DC
        monitoring.region
        logging_region
        swift.backup.endpoint
        domain
        BACKUP_TIME
        oauth2.discovery.url
        ssl.deploy.process
        service.broker.endpoint
        authorization.key

    Args:
        datacenter (str): the softlayer datacenter shortname, ie: Dal09, par01, etc
        target (str): the target environment name

    """
    defaults = {}
    key = datacenter.lower()
    city = sl.get_dc_city(key)
    defaults['DC'] = datacenter
    defaults['monitoring.region'] = city
    region = sl.get_dash_logging_region(key)
    defaults['logging_region'] = region
    defaults['swift.backup.endpoint'] = sl.get_dash_swift_endpoint(key)
    defaults['domain'] = sl.PUBLIC_SERVICES_DOMAINS[region]
    defaults['BACKUP_TIME'] = sl.BACKUP_TIME_MAPPING[city]
    defaults['oauth2.discovery.url'] = cli.OAUTH2_DISCOVER_URL[region]
    defaults['ssl.deploy.process'] = cli.SSL_DEPLOY_PROCESS[region]
    defaults['service.broker.endpoint'] = cli.SERVICE_BROKER[region]

    if region == 'US_South':
        auth_parent = 'YP'
    elif region == 'United_Kingdom':
        auth_parent = 'LYP'
    else:
        auth_parent = 'SYP'

    auth_props = cli.get_component_env_props('dynamite-controller', auth_parent)

    defaults['authorization.key'] = auth_props['authorization.key']

    print 'Setting up default public bluemix settings for %s' % city
    print json.dumps(defaults, sort_keys=True, indent=2)

    for key in defaults.keys():
        cli.setcomponentenvprop(target, 'dynamite-controller', key, defaults[key])


domain = 'dashdb.cdsdev.net'
comp = 'dynamite-controller'
order = {}
ucdnodes = []
capturejson = {}
if __name__ == "__main__":
   main(sys.argv[1:])

