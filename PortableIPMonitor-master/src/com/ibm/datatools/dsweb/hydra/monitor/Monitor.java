package com.ibm.datatools.dsweb.hydra.monitor;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import com.cloudant.client.api.CloudantClient;
import com.cloudant.client.api.Database;
import com.cloudant.client.api.View;
import com.ibm.datatools.dsweb.controller.HydraException;
import com.ibm.datatools.dsweb.repository.PortableIP;
import com.ibm.datatools.dsweb.repository.Vlan;
import com.ibm.datatools.dsweb.repository.VlanAvailability;


public class Monitor{
	
	private	static String	cloudantUser_	=	System.getenv("cloudant_user");
	private	static String	cloudantPwd_	=	System.getenv("cloudant_pass");
    
	static CloudantClient client = null;
	
	public static void initializeCloudantClient()
	{
		try {
			client = new CloudantClient(cloudantUser_, cloudantUser_,
					cloudantPwd_);
		} catch (org.lightcouch.CouchDbException e) {
			throw new HydraException(
					"Unable to connect to Monitor repository", e);
		}
	}




	public static List<Vlan> getVlans() {
		if(client == null)
		{
			initializeCloudantClient();
		}
		
		List<Vlan> vlans = new ArrayList<Vlan>();
		View vw =  client.database("portableip",false).view("aggregates/byvlan");
		List<com.google.gson.JsonObject> vlanObjects = vw.group(true).query(com.google.gson.JsonObject.class);
		for ( com.google.gson.JsonObject o : vlanObjects ) {
				Vlan vlan = new Vlan();
				vlan.setVlan(o.get("key").getAsString());
				vlans.add(vlan);
			}
			
		System.out.println("Found vlans " + vlans);
		
		return vlans;

	}
	
	public static Map<String,VlanAvailability> getPortableIPCountByDeploymentZones() {
		
		if(client == null)
		{
			initializeCloudantClient();
		}
		
		List<Vlan> dzs = getVlans();
		List<PortableIP> portableIps = getAllPortableIPs();
		
		Map<String,Vlan> dznames = new HashMap<String,Vlan>();
		for(Vlan dz : dzs)
		{
			dznames.put(dz.getVlan(), dz);
		}
		
		Map<String,VlanAvailability> dza = new HashMap<String, VlanAvailability>();
		for(PortableIP portableIp : portableIps)
		{
			if(portableIp.get_id().startsWith("_design"))
			{
				continue;
			}
			
			VlanAvailability dzarecord = null;
			if(dza.containsKey(portableIp.getVlan()))
			{
				dzarecord = dza.get(portableIp.getVlan());
			}
			else
			{
				dzarecord = new VlanAvailability();
				dzarecord.setVlan(dznames.get(portableIp.getVlan()));
				dza.put(portableIp.getVlan(), dzarecord);
			}

//			Zombie: reserved = True, available = True
//			In Use: reserved = True, available = False 
//			Available:  reserved = False, available = True 
//			Unavailable: reserved = False, available = False  


			if(portableIp.isUsed())
			{
				dzarecord.setInuse(dzarecord.getInuse() + 1);
			}
			else
			{
				dzarecord.setAvailable(dzarecord.getAvailable() + 1);
			}
			
			dzarecord.setTotal(dzarecord.getTotal() + 1);
		}
		
		return dza;
	}
	
	public static List<PortableIP> getPortableIPsForVlan(String DZId){
		
		if(client == null)
		{
			initializeCloudantClient();
		}
		
		Database portables = client.database("portableip", false);
		List<PortableIP> portableIPs = portables.findByIndex(
				"\"selector\": " +
                "{\"vlan\": " + DZId + "}",
                PortableIP.class);
		
		return portableIPs;
		
	}
	
	
	public static List<PortableIP> getAllPortableIPs(){
		
		if(client == null)
		{
			initializeCloudantClient();
		}
		
		Database portables = client.database("portableip", false);
		List<PortableIP> portableIPs = portables.view("_all_docs").includeDocs(true).query(PortableIP.class);
		
		return portableIPs;
		
	}
	
	
}
