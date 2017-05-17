package com.ibm.datatools.dsweb.controller;

public class HydraException extends RuntimeException {
	
	private String message = null;

	public HydraException(String message, Throwable cause) {
		super(message, cause);
		
	}

	public HydraException(String message) {
		super(message);
		
	}

	

}
