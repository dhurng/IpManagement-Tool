package com.ibm.datatools.dsweb.repository;

public class PortableIP {

	private String _id;
	private String _rev;
	private String status;
	private boolean used;
	private String ip_id;
	private String ip;
	private String vlan;
	private String vlanid;

	public String get_id() {
		return _id;
	}
	public void set_id(String _id) {
		this._id = _id;
	}
	public String get_rev() {
		return _rev;
	}
	public void set_rev(String _rev) {
		this._rev = _rev;
	}
	public String getStatus() {
		return status;
	}
	public void setStatus(String status) {
		this.status = status;
	}
	public boolean isUsed() {
		return used;
	}
	public void setUsed(boolean used) {
		this.used = used;
	}
	public String getIp_id() {
		return ip_id;
	}
	public void setIp_id(String ip_id) {
		this.ip_id = ip_id;
	}
	public String getIp() {
		return ip;
	}
	public void setIp(String ip) {
		this.ip = ip;
	}
	public String getVlan() {
		return vlan;
	}
	public void setVlan(String vlan) {
		this.vlan = vlan;
	}
	public String getVlanid() {
		return vlanid;
	}
	public void setVlanid(String vlanid) {
		this.vlanid = vlanid;
	}

}
