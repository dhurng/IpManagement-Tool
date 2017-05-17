#!/usr/bin/python
# -*- coding: utf-8 -*-
"""A collection of functions for interacting with UCD via the udclient.  Expects the udclient to be installed and
configured correctly.  Will take an access token for auth if one isn't in the environment when the process
starts.
"""

OAUTH2_DISCOVER_URL = {
    'United_Kingdom'    : 'https://api.eu-gb.bluemix.net/info',
    'US_South'          : 'https://api.ng.bluemix.net/info',
    'Sydney'            : 'https://api.au-syd.bluemix.net/info'
}
"""Mapping of public bluemix regions to OAUTH2 discovery URLs.
"""

SSL_DEPLOY_PROCESS = {
        'United_Kingdom'    : 'Deploy eu-gb SSL certificate',
        'US_South'          : 'Deploy dal SSL certificate',
        'Sydney'            : 'Deploy au-syd SSL certificate'
}
"""Mapping of public bluemix regions to SSL deploy processes
"""

SERVICE_BROKER = {
    'United_Kingdom'    : 'https://dashdb-repo-lyp.cloudant.com/providers',
    'US_South'          : 'https://dashdb-repo-yp.cloudant.com/providers',
    'Sydney'            : 'https://dashdb-repo-syp.cloudant.com/providers'
}
"""Mapping of public bluemix regions to service broker endpoints
"""

import json,os,sys,shutil,requests,re,time,math,copy
from common import util

DEBUG = False
#########

def udcli(clicommand):
    """Wrapper around the call to udclient, takes the request string and strips away
    any garbage in stdout when the udclient is configured to connect via proxy which
    gets in the way of json parsing.

    Args:
        clicommand (str): the preformatted command to be run via udclient

    Returns:
        str: output of the udclient command, usually either json or a single string

    Raises:
        SystemExit: util.run_command will raise SystemExit if the udclient command is malformed
            or if the command would otherwise have returned non-zero.  This function will not
            catch that exception and its expected that higher level calls are going to deal with
            it (or not).

    """
    command = "udclient -v %s" % (clicommand)
    (stdout,stderr,rc) = util.run_command(command)
    cleaned = re.sub('Using \d+ for proxy port.', '', stdout).strip()
    #print(stdout)
    #print(stderr)
    return cleaned

#########

def order_environments(envs):
    """Orders environments based on a sorted list of ids.

    Args:
        envs (list): list of strings of environment IDs sorted in the order to save the new ordering in

    """
    base_url = 'https://ucdeploy.swg-devops.com/rest/deploy/application/7b0272e0-8cf4-4d54-9476-4e7bafac34c2/orderEnvironments'
    r = requests.put(base_url, data=json.dumps(envs), auth=('PasswordIsAuthToken', '{"token":"%s"}' % os.environ["DS_AUTH_TOKEN"]))
    if r.status_code is not 200:
        raise SystemExit(1)

#########

def move_resource(resource, newparent):
    """Moves a base resource to a new parent resource.

    Args:
        resource (str): the path to the resource to be moved
        newparent (str): the new parent resource

    Examples:
        >>> move_resource('/CDS dashDB/UnderConstruction/AWS-USWest2-dashdb-mpp-pentest-uswest2-03','/CDS dashDB/AWS-USWest2')

    """
    udcli('moveResource -resource "%s" -parent "%s"' % (resource, newparent))


def move_child_resources(parent, newparent):
    """Moves all child resources from the parent to a new parent resource.

    Args:
        parent (str): the current parent resource path
        newparent (str): the path to the new parent resource

    Example:
        >>> move_child_resources('/CDS dashDB/UnderConstruction / DoNotUpdate/CDS-Dev', '/CDS dashDB/CDS-Dev')

    """
    subresources = json.loads(udcli("getResources -parent '%s'" % parent))
    for resource in subresources:
        move_resource(resource['path'], newparent)

#########

def blueprint_exists(blueprint):
    """Checks the `myapplication` UCD application if the `blueprint` exists and
    returns `True` or `False`

    Args:
        blueprint (str): the name of the blueprint to check

    Returns:
        bool: if the blueprint exists or not

    """
    blueprints = json.loads(udcli('getBlueprintsInApplication -application "%s"' % myapplication))
    names = [x['name'] for x in blueprints]
    return blueprint in names

#########

def get_env_blueprint(env):
    """Some hackery to get the blueprint name of an environment since
    its not a supported API from UCD

    Args:
        env (str): the environment name

    Returns:
        str: the name of the blueprint for the given environment

    Raises:
        SystemExit: Like most of these functions if they don't work
        they raise the SystemExit (return non-zero) exception which can be
        caught, but this one does it explicitly (most of these are doing it
        via the util module)

    """
    base_url = 'https://ucdeploy.swg-devops.com/rest/deploy/environment/'
    envdata = get_env(env)
    envid = envdata["id"]
    r = requests.get(base_url + envid, auth=('PasswordIsAuthToken', '{"token":"%s"}' % os.environ["DS_AUTH_TOKEN"]))
    if r.status_code is not 200:
        raise SystemExit(1)

    blueprint = ''
    try:
        blueprint = r.json()["blueprint"]
    except KeyError:
        raise SystemExit(1)
    return blueprint["name"]

#########

def get_env(env):
    """A very thin vineer around udclient getEnvironment

    Args:
        env (str): environment name

    Returns:
        json: the UCD json object for getEnvironment

    """
    envdata = json.loads(udcli('getEnvironment -application "%s" -environment "%s"' % (myapplication, env)))
    return envdata


#########

def get_relay_zones():
    """Gets a list of UCD Relay Zones, useful for determining if new ones show up maybe
    as well as if there is something special about your particular zone (ie US-FED has
    a unique endpoint for Softlayer which we could leverage this to determine if we need
    change our api endpoint)

    Returns:
        json: sorta, its a list of json objects which json.loads doesn't do well with

    """
    # Excuse this magic string here....
    command = 'curl -Ss https://i5S9kZic6vaYjlikf2pboQIHaXUzMEzavtilknrWx5KSsWkPEwPTPptrC3RainJX16sxo13PXoGiTe7KPlMUbw==@cdsmon-infra-services-proxy.mybluemix.net/cdsmon-infra-services/api/ucd/properties/UCDRELAYZONES-PROVISION'
    (stdout,stderr,rc) = util.run_command(command)
    zones = json.loads(stdout)
    return zones

def get_my_relay_zone(my_zone_name):
    """Gets just the relay zone details for a particular given name.

    Args:
        my_zone_name (str): the name of the relay zone

    Return:
        json: the relay zone details

    """
    zones = get_relay_zones()
    zones = zones['zones']
    for zone in zones:
        if zone['name'] == my_zone_name:
            return zone

#########

@util.run_once
def set_token(token):
    """Sets the os environment variable DS_AUTH_TOKEN used by the udclient
    to authorize us against the ucd server.  Should be given to most top level
    scripts that use the ucd module and set before any of the ucd functions 
    are used

    Args:
        token (str): the authorization token

    """
    os.environ["DS_AUTH_TOKEN"] = token


######### 
def restrict_env_to_prod(env):
    """Utility / legacy function because I'm too lazy to go back and find where I used this function before I fixed it to be generic.  Calls restrict_env with the environment given and feeds it *'Production Environment'*
    Args:
        env (str): name of the environment

    """
    restrict_env(env, 'Production Environment')

def get_env_base_resources(env):
    """Gets an environment's base resources.

    Args:
        env (str): the environment's name

    Returns:
        array of json objects

    """
    baseResources = json.loads(udcli("getEnvironmentBaseResources -application '%s' -environment '%s'" % (myapplication, env)))
    return baseResources

#########
def restrict_env(env, role):
    """Takes an environment name and an environment role like
    *Production Environment* and restricts the environment to only
    that role for **myteam**.  Additionally restricts any resources and agents
    associated with the environment to a similar role (Production Environment =
    Production Resource = Production Agent) etc.

    Args:
        env (str): name of the environment
        role (str): name of a role or type to restrict the environment to.
            For example, if you want the environment to be only a member of
            **CDS dashDB(as a Production Environment)** then the role would be
            *'Production Environment'*

    """
    teams = json.loads(udcli("getEnvironment -application '%s' -environment '%s'" % (myapplication, env)))["extendedSecurity"]["teams"]
    udcli("addEnvironmentToTeam -application '%s' -environment '%s' -team '%s' -type '%s'" % (myapplication, env, myteam, role))
    for team in teams:
        if team.has_key("resourceRoleLabel"):
            if team["teamLabel"] == myteam and team["resourceRoleLabel"] == role:
                continue
            else:
                udcli("removeEnvironmentFromTeam -application '%s' -environment '%s' -team '%s' -type '%s'" % (myapplication, env, team["teamLabel"], team["resourceRoleLabel"]))
        else:
            udcli("removeEnvironmentFromTeam -application '%s' -environment '%s' -team '%s'" % (myapplication, env, team["teamLabel"]))

    # Now restrict the resources
    baseResources = json.loads(udcli("getEnvironmentBaseResources -application '%s' -environment '%s'" % (myapplication, env)))
    for resource in baseResources:
        res = json.loads(udcli("getResource -resource '%s'" % resource['id']))
        restrict_resource(res, role.replace('Environment', 'Resource'))

#########  Smells like copy pasta in the morning
def restrict_agent(agent, role):
    """Takes a agent and restricts that agent to the role provided.

    Args:
        agent (json): a UCD agent in json form, expected output from 
            udcli getAgent
        role (str): a team role like 'Production Environment' that we're
            restricting the agent to

    """
    udcli("addAgentToTeam -agent '%s' -team '%s' -type '%s'" % (agent['id'], myteam, role))
    teams = agent["extendedSecurity"]["teams"]
    for team in teams:
        if team.has_key("resourceRoleLabel"):
            if team["teamLabel"] == myteam and team["resourceRoleLabel"] == role:
                continue # Keep this one (we just added it)
            else: # Remove the role type we don't want
                udcli("removeAgentFromTeam -agent '%s' -team '%s' -type '%s'" % (agent['id'], team["teamLabel"], team["resourceRoleLabel"]))
        else: # Remove the team (no type)
            udcli("removeAgentFromTeam -agent '%s' -team '%s'" % (agent['id'], team["teamLabel"]))

#########
def restrict_resource(resource, role):
    """Takes a resource and restricts that resource to the role provided.
    Then recursively restricts any subresources.  If it finds an agent it 
    restricts that as well.

    Args:
        resource (json): a UCD resource in json form, expected output from 
            udcli getResource
        role (str): a team role like 'Production Environment' that we're
            restricting resources and agents too

    """
    validresources = ['subresource', 'agent'] 
    # End the recursion
    if resource['type'] not in validresources:
        return

    # Restrict this resource, but first add the one we actually want
    udcli("addResourceToTeam -resource '%s' -team '%s' -type '%s'" % (resource['id'], myteam, role))
    teams = resource["extendedSecurity"]["teams"]
    for team in teams:
        if team.has_key("resourceRoleLabel"):
            if team["teamLabel"] == myteam and team["resourceRoleLabel"] == role:
                continue # Keep this one (we just added it)
            else: # Remove the role type we don't want
                udcli("removeResourceFromTeam -resource '%s' -team '%s' -type '%s'" % (resource['id'], team["teamLabel"], team["resourceRoleLabel"]))
        else: # Remove the team (no type)
            udcli("removeResourceFromTeam -resource '%s' -team '%s'" % (resource['id'], team["teamLabel"]))

    # Check if this is an agent resource, if so restrict the agent as well
    if resource['type'] == 'agent':
        agent = json.loads(udcli("getAgent -agent '%s'" % resource['agent']['id']))
        restrict_agent(agent, role.replace('Resource', 'Agent')) # Lets not do this quite yet, since we're sharing toolserver agents

    # Now find any subresources and recurse through them
    subresources = json.loads(udcli("getResources -parent '%s'" % resource['id']))
    for subresource in subresources:
        res = json.loads(udcli("getResource -resource '%s'" % subresource['id']))
        restrict_resource(res, role)

#########
def get_agents_from_resource(resource):
    """Returns a list of all agent ids under this resource.

    Args:
        resource (json): a UCD resource in json form, ecpected output from
        udcli getResource

    Returns:
        array: List contains all agent IDs that show up under this resource tree
            as agent resources.

    """
    result = []
    if resource['type'] == 'agent':
        agent = json.loads(udcli("getAgent -agent '%s'" % resource['agent']['id']))
        result.append(agent['id'])

    subresources = json.loads(udcli("getResources -parent '%s'" % resource['id']))
    for subresource in subresources:
        res = json.loads(udcli("getResource -resource '%s'" % subresource['id']))
        result = list(set(result + get_agents_from_resource(res)))

    return result

#########
def get_agents_from_environment(env):
    """Returns a list of all agent ids under a given environment.

    Args:
        env (str): the environment name

    Returns:
        array: List contains all agent IDs that show up under the environment
    
    """
    result = []
    baseResources = json.loads(udcli("getEnvironmentBaseResources -application '%s' -environment '%s'" % (myapplication, env)))
    for resource in baseResources:
        res = json.loads(udcli("getResource -resource '%s'" % resource['id']))
        result = list(set(result + get_agents_from_resource(res)))
    return result

#########

def get_toolserver_agentid(env):
    """Brute force searches for an agent in the environment matching the dashdb-<>-toolserver
    pattern

    Args:
        env (str): name of the environment to search for

    Returns:
        str: the agent id of the toolserver agent for the environment (if it exists or None)

    """
    agents = get_agents_from_environment(env)
    for agent in agents:
        details = json.loads(udcli("getAgent -agent '%s'" % agent))
        if details['name'].startswith('dashDB') and details['name'].endswith('toolserver'):
            return agent
    return None

#########
def replace_tokens(token, replacement, json_file):
    """Utility function to replace some tokens in a json file.  Really this shouldn't be
    here and should exist in the util module (if it doesn't already exist there).

    Args:
        token (str): the token to replace
        replacement (str): the string to replace the token with
        json_file (str): partial filename indicating which file to replace the
            token in with the replacement

    """
    tempid = util.gen_id()
    outfile = "%s/work/%s/%s" % (scriptdir, runid, tempid)
    fqjson = "%s/work/%s/%s" % (scriptdir, runid, json_file)
    with open(outfile, "wt") as fout:
        with open(fqjson, "rt") as fin:
            for line in fin:
                fout.write(line.replace(token, replacement))
    shutil.move(outfile, fqjson)
    return fqjson

#########
# Only copies insecure properties
def copy_component_environment_properties(component, source_env, target_env):
    """Copies component environment properties from one environment to
    another.  Does not copy secure properties.

    Args:
        component (str): the name of the component
        source_env (str): the name of the source environment
        target_env (str): the name of the target environment

    """
    props = json.loads(udcli("getComponentEnvironmentProperties -component '%s' -application '%s' -environment '%s'" % (component, myapplication, source_env)))
    for prop in props:
        if not prop['secure']:
            try:
                udcli("setComponentEnvironmentProperty -component '%s' -application '%s' -environment '%s' -name '%s' -value '%s'" % (component, myapplication, target_env, prop['name'], prop['value']))
            except SystemExit:
                pass

#########

@util.run_once
def gen_workdir():
    """Generates a work directory for modifying template json files

    """
    print("Generating template json and using working directory %s" % runid)
    shutil.copytree("%s/jsonTemplates" % scriptdir, "%s/work/%s" % (scriptdir, runid))

#########

def get_tmp_json_file():
    """Generates a unique filename for temporary file token replacement.

    """
    gen_workdir()
    workdir = '%s/work/%s' % (scriptdir, runid)
    return '%s/%s.json' % (workdir, util.gen_id())

#########

def get_env_prop(env, prop):
    """Thin vineer around getEnvironmentProperty

    Args:
        env (str): the environment name
        prop (str): the property name

    Returns:
        str: the property value for prop

    """
    return udcli("getEnvironmentProperty -application '%s' -environment '%s' -name '%s'" % (myapplication, env, prop))

#########

def get_env_props(env):
    """Thin vineer around getEnvironmentProperties

    Args:
        env (str): the environment name

    Returns:
        list: the environment property sheet as a list of json entries

    """
    return json.loads(udcli("getEnvironmentProperties -application '%s' -environment '%s'" % (myapplication, env)))

#########

def submit_process(process, env, onlyChanged=True, properties=None, snapshot=None, versions=None):
    """Submits an application process.

    Args:
        process (str): the application process
        env (str): environment name
        onlyChanged (Optional[bool]): Defaults to True.
        properties (Optional[json]): Defaults to None.  If used it should look
            like ``properties={'prop1': 'value1', 'prop2': 'value2'}``
        snapshot (Optional[str]): Defaults to None.  If given, versions should not be used.
        versions (Optional[list]): Defaults to None. If given, snapshot should not be used.
            If used should look like versions=[{'component': 'Component name or ID',
            'version': 'Version name or ID'}]

    Returns:
        str: request id for the submitted process

    """
    template = { 'application': myapplication,
                'applicationProcess': process,
                'environment': env,
                'onlyChanged': onlyChanged }
    if properties is not None:
        template['properties'] = properties
    if snapshot is not None:
        template['snapshot'] = snapshot
    elif versions is not None:
        template['versions'] = versions
    print template

    jsonfile = get_tmp_json_file()
    with open(jsonfile, "w+") as fout:
        json.dump(template, fout)
    response = eval(udcli('requestApplicationProcess %s' % jsonfile))
    return response['requestId']

#########

def get_process_status(process):
    """Gets the process request status json object for a given request id

    Args:
        process (str): request id

    Returns:
        json: process request status for the given request id

    """
    return json.loads(udcli('getApplicationProcessRequestStatus -request %s' % process))

#########

def get_app_prop(propname):
    """Thin vineer around getApplicationProperty

    Args:
        propname (str): the name of the application property to fetch

    Returns:
        str: the value of propname in myapplication

    """
    return udcli('getApplicationProperty -application %s -name %s' % (myapplication, propname))

#########

def delete_app_prop(propname):
    """Tricky little hackery to delete an application property since there isn't
    an API for it

    Its possible that this function *may* not delete the application property as there is
    an inherent race condition in the way UCD delete's application properties.  In order
    to delete application properties you must have in your headers "version" with the current
    property sheet version for the application.  Its possible that during the call to get the
    current property sheet and the request to delete a property someone updates the properties
    and we lose the race and fail our delete.  If this becomes problematic we may have to revisit
    this and add some retry logic.

    Given that this will raise a process terminating exception in the event of a failure and
    there is a race condition built in... caveat emptor.

    Args:
        propname (str): the name of the property to delete

    Raises:
        SystemExit: As most of these functions do, if unsuccessful it will raise SystemExit,
            this one just happens to do it directly rather than indirectly via a lower level
            function call.

    """
    appID = json.loads(udcli("getApplication -application %s" % myapplication))['id']
    auth=('PasswordIsAuthToken', '{"token":"%s"}' % os.environ["DS_AUTH_TOKEN"])
    baseURL = 'https://ucdeploy.swg-devops.com/property/propSheet/applications&'
    propsheet = requests.get('%s%s&propSheet.-1' % (baseURL, appID), auth=auth)
    if propsheet.status_code != 200:
        print 'Failed to retrieve current application property sheet'
        raise SystemExit(1)
    currentVersion = propsheet.json()['version']
    response = requests.delete('%s%s&propSheet.-1/propValues/%s' % (baseURL, appID, propname), auth=auth, headers={'version': '%s' % currentVersion})
    if response.status_code != 200:
        print 'Failed to delete', propname
        raise SystemExit(1)
    print propname, 'successfully deleted from', myapplication

#########

def add_base_resource(env, resource):
    """Thin vineer around addEnvironmentBaseResource

    Args:
        env (str): environment name
        resource (str): resource ID to add to the environment

    """
    return udcli("addEnvironmentBaseResource -environment '%s' -application '%s' -resource '%s'" % (env, myapplication, resource))

#########

def submit_and_wait(process, env, onlyChanged=True, properties=None, snapshot=None, versions=None, delay=30):
    """Wrapper around submit process function and then waits for it to complete.

    Args:
        process (str): the application process
        env (str): environment name
        onlyChanged (Optional[bool]): Defaults to True.
        properties (Optional[json]): Defaults to None.  If used it should look
            like ``properties={'prop1': 'value1', 'prop2': 'value2'}``
        snapshot (Optional[str]): Defaults to None.  If given, versions should not be used.
        versions (Optional[list]): Defaults to None. If given, snapshot should not be used.
            If used should look like versions=[{'component': 'Component name or ID',
            'version': 'Version name or ID'}]
        delay (Optional[int]): Defaults to 30. How frequently to check for updates on the
            status of the process

    Raises:
        SystemExit: If the process we were waiting on fails, we just send a non-zero up the chain

    """
    process_id = submit_process(process, env, onlyChanged=onlyChanged, properties=properties, snapshot=snapshot, versions=versions)
    result = wait_on_process(process_id, delay)
    if result['status'] != 'CLOSED' or result['result'] != 'SUCCEEDED':
        print 'Error: Process request failed! Clean up any left over artifacts and retry'
        raise SystemExit(1)

#########

def wait_on_process(process, delay=30):
    """Waits on a process request till it completes.

    Args:
        process (str): request id that we want to wait on
        delay (Optional[int]): Defaults to 30. Delay between checks in seconds

    Returns:
        json: Returns the final json status

    """
    states = ['EXECUTING', 'PENDING']
    status = get_process_status(process)
    print 'Checking the status of %s/#applicationProcessRequest/%s' % (os.environ['DS_WEB_URL'] , process)
    while (status['status'] in states):
        time.sleep(delay)
        print 'Checking the status of %s/#applicationProcessRequest/%s' % (os.environ['DS_WEB_URL'] , process)
        status = get_process_status(process)
        print status['status']

    print 'Stauts: %s, Final result: %s' % (status['status'], status['result'])
    return status



#########

def delete_environment(env, resources = True, agents = True):
    """Deletes an environment, by default also deletes attached resources

    Args:
        env (str): the environment name
        resources (Optional[bool]): Defaults to True. Delete the attached resources (or not)

    """
    res = ''
    if agents:
        delete_agents_from_env(env)
    if resources:
        res = "-deleteAttachedResources True"
    return udcli("deleteEnvironment -application '%s' -environment '%s' %s" % (myapplication, env, res))

#########
# Your agent better conform to the "application-environment-role" naming convention..

def delete_agent(env, role = None):
    """This is total garbage, redo this based on the restrict method of walking down the
    resource tree and finding the agent from the environment base resources and deleting them that
    way.

    """
    agentname = '%s-%s' % (myapplication, env)
    if role is not None:
        agentname += '-%s' % role
    return udcli('deleteAgent -agent %s' % agentname)

#########

def delete_agents_from_env(env):
    """Walks the resource tree of an environment finding any agent resources and
    deletes the corresponding agents for those resources.

    Args:
        env (str): the environment to search for agent references

    """
    agents = get_agents_from_environment(env)
    for agent in agents:
        udcli('deleteAgent -agent %s' % agent)

def setapplicationprop(propname, propvalue):
    """Thin vineer around setApplicationProperty

    Args:
        propname (str): the application property name to set
        propvalue (str): the value to set for the application property

    """
    command = "setApplicationProperty -application '%s' -name '%s' -value '%s'" % (myapplication, propname, propvalue)
    udcli(command)

#########

def set_agent_prop(agent, propname, propvalue, secure=False):
    """Thin vineer around setAgentProperty

    Args:
        agent (str): the name or ID of the agent
        propname (str): the property name
        propvalue (str): the value of the property to set
        secure (Optional[bool]): Defaults to False. If the property is secure or not.

    """
    command = "setAgentProperty -agent '%s' -name '%s' -value '%s'" % (agent, propname, propvalue)
    if secure:
        command += ' -isSecure true'
    udcli(command)

#########

def get_agent_prop(agent, propname):
    """Gets the value of a particular property from the specified agent

    Args:
        agent (str): the id of the agent
        propname (str): the name of the property to look up

    Returns:
        str: the value of the property

    """
    return udcli("getAgentProperty -agent '%s' -name '%s'" % (agent, propname))

#########

def setcomponentenvprop(env, component, propname, propvalue, secure=False):
    """Thin vineer around setComponentEnvironmentProperty

    Args:
        env (str): the environment name
        component (str): the component name
        propname (str): the property name
        propvalue (str): the property value
        secure (Optional[bool]): Defaults to False. If the property is secure or not.

    """
    command = "setComponentEnvironmentProperty -component '%s' -application '%s' -environment '%s' -name '%s' -value '%s'" % (component, myapplication, env, propname, propvalue)
    if secure:
        command += ' -isSecure true'
    udcli(command)

#########

def get_component_env_props(component, env):
    """Get component environment properties for an environment

    Args:
        component (str): the component name
        env (str): the environement name

    Returns:
        dict: name value pairs of properties

    """
    command = "getComponentEnvironmentProperties -application '%s' -environment '%s' -component '%s'" % (myapplication, env, component)
    props = {}
    data = json.loads(udcli(command))
    for value in data:
        props[value['name']] = value['value']
    return props

#########

def setenvprop(env, propname, propvalue, secure=False):
    """Thin vineer around setEnvironmentProperty

    Args:
        env (str): the environment name
        propname (str): the property name
        propvalue (str): the property value
        secure (Optional[bool]): Defaults to False. If the property is secure or not.

    """
    command = "setEnvironmentProperty -application '%s' -environment %s -name '%s' -value '%s'" % (myapplication, env, propname, propvalue)
    if secure:
        command += ' -isSecure true'
    udcli(command)

#########

def generate_sl_mpp_json(contact, map_key, node_count, role='node', nodeid_start = 1):
    """Generates a UCD specific SL provisioning pattern json template for
    dashDB MPP given a particular node pattern and a node count.

    Args:
        contact (str): User contact for the node pattern (this will show up in the
            Softlayer notes field.
        pattern (str): the name of the pattern matching the json template in
            jsonTemplates that describe the layout of the nodes
        node_count (int): the number of nodes to deploy
        role (Optional[str]): the role to use when generating the json template,
            default is 'node'
        nodeid_start (Optional[str]): starting node id, default is 1

    """
    mapping = {
        'Regular Node BM' : 'bm_mpp',
        'Regular Node VM' : 'vm_mpp',
        'Regular Node VM CentOS 7' : 'vm_mpp_centos7',
        'Super Node BM' : 'bm_supernode',
        'Super Node VM' : 'vm_mpp64',
        'Regular Node 64GB VM' : 'vm_mpp64',
        'Super Node BM Backup' : 'bm_backup',
        'Super Node VM Backup' : 'vm_backup'
    }
    backup_drive_json = 'backup_drive_snippet'
    backup_raid_json = 'backup_raid_snippet'
    backup = False
    nodes = {
        'parameters' : []
    }
    if not mapping.has_key(map_key):
        print 'ERROR: Unable to find mapping to json template for %s' % map_key
        exit(1)

    index_type = 'vm_index'
    if 'BM' in map_key:
        index_type = 'bm_index'

    pattern = mapping[map_key]
    info = 'Contact: %s UrbanCode Deploy Server: https://ucdeploy.swg-devops.com' % contact
    with open('%s/jsonTemplates/%s.json' % (scriptdir, pattern)) as json_file:
        node_base_pattern = json.load(json_file)

    # Only order enough drives...
    if map_key.endswith('Backup') and index_type == 'bm_index':
        backup = True
        dash_nodes = node_count
        total_arrays = dash_nodes + 1 #metadata
        ARRAYS_PER_NODE = 5
        DRIVE_START_INDEX = 2
        DRIVES_PER_ARRAY = 5
        node_count = int(math.ceil(float(node_count) / float(ARRAYS_PER_NODE)))
        with open('%s/jsonTemplates/%s.json' % (scriptdir, backup_drive_json)) as json_file:
            backup_drive_pattern = json.load(json_file)
        with open('%s/jsonTemplates/%s.json' % (scriptdir, backup_raid_json)) as json_file:
            backup_raid_pattern = json.load(json_file)
    elif map_key.endswith('Backup'):
        node_count = int(math.ceil(float(node_count) / 5.0))

    for node in range(nodeid_start, node_count + nodeid_start):
        node_role = '%s%s' % (role, node)
        ucd_parms = {
            index_type : node,
            'notes' : info,
            'role' : node_role,
            'tags' : 'cds:service:dash'
        }
        node_pattern = copy.deepcopy(node_base_pattern)
        node_pattern['ucd_parms'] = ucd_parms

        # If we have a bm backup config, do fancy stuff...
        if backup:
            drive_index = DRIVE_START_INDEX
            if node == 1:
                ARRAYS_PER_NODE = 6 # because metadata... I know... constant...
            else:
                ARRAYS_PER_NODE = 5
            if (total_arrays // ARRAYS_PER_NODE) > 0:
                arrays = ARRAYS_PER_NODE
            else:
                arrays = total_arrays
            total_arrays -= arrays
            drives = DRIVES_PER_ARRAY * arrays
            for i in range(drives):
                node_pattern['prices'].append(backup_drive_pattern)
            for a in range(1, arrays + 1):
                raid_drives = range(drive_index, drive_index + DRIVES_PER_ARRAY)
                drive_index += DRIVES_PER_ARRAY
                array_raid = copy.deepcopy(backup_raid_pattern)
                array_raid['hardDrives'] = raid_drives
                array_raid['partitions'][0]['name'] = '/disk%s' % a
                node_pattern['storageGroups'].append(array_raid)

        nodes['parameters'].append(node_pattern)

    if DEBUG:
        print json.dumps(nodes, sort_keys=True, indent=2)
    return nodes

#########

def setapplicationprop_by_rest(name, value):
    """Sets an application property by rest call rather than udcli (for when its a really, really large
    JSON template that wont work on the command line.

    Args:
        name (str): the name of the property
        value (str): the value of the property

    """
    base_url = 'https://ucdeploy.swg-devops.com/property/propSheet/applications%267b0272e0-8cf4-4d54-9476-4e7bafac34c2%26propSheet.-1'
    auth=('PasswordIsAuthToken', '{"token":"%s"}' % os.environ["DS_AUTH_TOKEN"])
    propsheet = requests.get(base_url, auth=auth)
    if propsheet.status_code != 200:
        print 'Failed to retrieve current application property sheet'
        raise SystemExit(1)
    currentVersion = propsheet.json()['version']
    if DEBUG:
        print 'Found current version of property sheet of %s' % currentVersion
    payload = {
        'name': name,
        'description': '',
        'secure': 'false',
        'value' : value
    }
    if DEBUG:
        print json.dumps(payload, sort_keys = True, indent = 2)
    r = requests.put(base_url + '/propValues', auth=auth, data=json.dumps(payload), headers = {'version': '%s' % currentVersion})
    if r.status_code != 200:
        print 'Failed to set application property %s, got return code of %s' % (name, r.status_code)
        raise SystemExit(1)
    if DEBUG:
        print json.dumps(r.json(), indent = 2, sort_keys = True)

#########

def color_environment(environment, color):
    """Changes the color of an environment.

    Args:
        env (str): the id of the environment
        color (str): the color in hex format `#FF0000 = red`

    """
    if DEBUG:
        print 'Coloring environment ID: %s as %s' % (environment, color)
    base_url = 'https://ucdeploy.swg-devops.com/rest/deploy/environment'
    url = '%s/%s' % (base_url, environment)
    auth=('PasswordIsAuthToken', '{"token":"%s"}' % os.environ["DS_AUTH_TOKEN"])
    r = requests.get(url, auth=auth)
    if r.status_code != 200:
        print 'Failed to get environment'
        raise SystemExit(1)
    # Build the put json
    base_env = r.json()
    if base_env['color'] != color:
        new_env = {
            "applicationId": base_env["application"]["id"],
            "color": color,
            "existingId": base_env["id"],
            "lockSnapshots": base_env["lockSnapshots"],
            "name": base_env["name"],
            "requireApprovals": base_env["requireApprovals"],
            "teamMappings": base_env["extendedSecurity"]["teams"]
        }

        if base_env.has_key("snapshotLockType"):
            new_env["snapshotLockType"] = base_env["snapshotLockType"]
        if base_env.has_key("cleanupCountToKeep"):
            new_env["cleanupCountToKeep"] = base_env["cleanupCountToKeep"]
            new_env["cleanupDaysToKeep"] = base_env["cleanupDaysToKeep"]
            new_env["inheritSystemCleanup"] = False
        else:
            new_env["inheritSystemCleanup"] = True
        if base_env.has_key("exemptProcesses"):
            new_env["exemptProcesses"] = base_env["exemptProcesses"]
        if base_env.has_key("description"):
            new_env["description"] = base_env["description"]

        try:
            r = requests.put(base_url, data=json.dumps(new_env), auth=auth)
            if r.status_code != 200:
                print 'Failed to put new env data!'
                #raise SystemExit(1)
                return r
        except requests.exceptions.ConnectionError:
            print 'Connection Error...'

#########

def main(argv):
    """Just something to run if someone calls this thing directly for some unknown reason
    """
    gen_workdir()
    udcli("getApplication -application dashDB")

# Globals
scriptdir = os.path.dirname(os.path.realpath(__file__))
myapplication = 'dashDB'
"""str: While this module is a little more generic than the aws one is this is still dash-deployment so
by default myapplication = 'dashDB'
"""

myteam = 'CDS dashDB'
"""str: The team this module uses when doing ucd tasks, default is 'CDS dashDB'
"""

if not os.path.exists("logs"):
    os.makedirs("logs")
if not os.path.exists("work"):
    os.makedirs("work")
runid = util.gen_id()

if __name__ == "__main__":
   main(sys.argv[1:])

