package com.ibm.datatools.dsweb.controller;

import java.util.HashSet;
import java.util.Set;

import org.apache.wink.common.WinkApplication;

public class PortableIPMonitorApplication
       extends WinkApplication
{
    private static final Set<Class<?>> classes = new HashSet<Class<?>>();

    static
    {
        classes.add(MonitorEndPoint.class);
    }

    @Override
    public Set<Class<?>> getClasses()
    {
        return classes;
    }
}