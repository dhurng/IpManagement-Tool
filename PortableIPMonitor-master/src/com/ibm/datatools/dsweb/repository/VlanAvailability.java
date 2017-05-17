package com.ibm.datatools.dsweb.repository;

public class VlanAvailability {
	
	private Vlan vlan;
	private int total = 0;
	private int available = 0;
	private int inuse = 0;
	
	public Vlan getVlan() {
		return vlan;
	}
	public void setVlan(Vlan vlan) {
		this.vlan = vlan;
	}
	public int getTotal() {
		return total;
	}
	public void setTotal(int total) {
		this.total = total;
	}
	public int getAvailable() {
		return available;
	}
	public void setAvailable(int available) {
		this.available = available;
	}
	public int getInuse() {
		return inuse;
	}
	public void setInuse(int inuse) {
		this.inuse = inuse;
	}
	
}
