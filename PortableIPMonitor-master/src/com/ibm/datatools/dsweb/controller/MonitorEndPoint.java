/**
o * Sample V2 Java jax-rs service broker.
 *
 * This sample can be deployed to CloudFoundry as an application as well.
 * If you have trouble deploying with Liberty, try the Java Tomcat buildpack:
 * <ul>
 * <li>cf push -b https://github.com/cloudfoundry/java-buildpack.git
 * </ul>
 *
 * The URL paths herein (other than the GET /) are mandated by CloudFoundry.
 */
package com.ibm.datatools.dsweb.controller;

import java.io.UnsupportedEncodingException;
import java.net.URISyntaxException;
import java.util.ArrayList;
import java.util.Enumeration;
import java.util.List;
import java.util.Map;
import java.util.Map.Entry;
import java.util.TreeMap;
import java.util.logging.Logger;

import javax.servlet.http.HttpServletRequest;
import javax.ws.rs.GET;
import javax.ws.rs.Path;
import javax.ws.rs.Produces;
import javax.ws.rs.QueryParam;
import javax.ws.rs.WebApplicationException;
import javax.ws.rs.core.Context;
import javax.ws.rs.core.MediaType;
import javax.ws.rs.core.Response;
import javax.ws.rs.core.Response.Status;
import javax.xml.bind.DatatypeConverter;

import org.apache.wink.json4j.JSONException;
import org.apache.wink.json4j.JSONObject;

import com.ibm.datatools.dsweb.hydra.monitor.Monitor;
import com.ibm.datatools.dsweb.repository.PortableIP;
import com.ibm.datatools.dsweb.repository.VlanAvailability;

@Path("/")
public final class MonitorEndPoint
{

  private static final String AUTHENTICATION_USER     = System.getenv("authentication_user");
  private static final String AUTHENTICATION_PASSWORD = System.getenv("authentication_password");

    private static final Logger LOGGER = Logger.getLogger(MonitorEndPoint.class.getName());

    private static Monitor monitor = null;

    /**
     * GET for testing.  Not invoked by CloudFoundry.
     * @throws JSONException
     * @throws UnsupportedEncodingException
     */
    @GET
    @Produces(MediaType.TEXT_HTML)
    @Path("portableIPs")
    public String getPortableIPs(@Context final HttpServletRequest httpServletRequest,
    						@QueryParam("vlan") final String vlan) throws JSONException, UnsupportedEncodingException
    {

    	System.out.println("Got request for portables for vlan : " + vlan + " from plain html");

    	StringBuffer buffer = new StringBuffer();
    	buffer.append("<html><head></head><body>");
    	buffer.append("<h3> Portable Ips for Vlan : " + vlan );
    	buffer.append("</h3></br>");
    	buffer.append("<table border=\"1\"><tr><th>ID</th><th>IP Address</th><th>Used</th><th>Status</th><th>Vlan</th><th>Comments</th></tr>");

    	List<PortableIP> portables = Monitor.getPortableIPsForVlan(vlan);

    	for(PortableIP portable:portables)
    	{

    		if(portable.isUsed())
    		{
    			buffer.append("<tr bgcolor=\"#FF9933\">");
    		}
    		else
    		{
    			buffer.append("<tr bgcolor=\"#66FF66\">");
    		}


    		buffer.append("<td>"+portable.getIp_id()+"</td>");
       	buffer.append("<td>"+ portable.getIp() +"</td>");
    		buffer.append("<td>"+ portable.isUsed() +"</td>");
    		buffer.append("<td>"+portable.getStatus() +"</td>");
    		buffer.append("<td>"+portable.getVlan() +"</td>" );
    		buffer.append("<td> </td>" );
    	}

    	buffer.append("</body></html>");
    	return buffer.toString();
    }


    @GET
    @Produces(MediaType.TEXT_HTML)
    public String getVLANs(@Context final HttpServletRequest httpServletRequest)
           throws URISyntaxException, JSONException
    {
        LOGGER.info("PortableIps GET request headers: " + headersString(httpServletRequest));

        validateAuthorization(httpServletRequest);

        StringBuffer buffer = new StringBuffer();

        Map<String, VlanAvailability> portableIPCountByDeploymentZones = monitor.getPortableIPCountByDeploymentZones();

        buffer.append("<html><head></head><body>");
    	buffer.append("<table border=\"1\"><tr><th>Vlan</th><th bgcolor=\"#66FF66\">Available</th><th bgcolor=\"#FF9933\">In Use</th><th>Total</th></tr>");

        for(Entry<String, VlanAvailability> dza : portableIPCountByDeploymentZones.entrySet())
        {
        	buffer.append("<tr><td><a href=\"/PortableIPMonitor/portableIPs?vlan="+dza.getKey()+"\">"+dza.getKey()+"</a></td>");

//        	if(dza.getValue().getVlan() != null)
//        	{
//        		buffer.append("<td>"+dza.getValue().getVlan().getVlan()+"</td>" );
//        	}
//        	else
//        	{
//        		buffer.append("<td>"+" "+"</td>" );
//        	}

    		buffer.append("<td bgcolor=\"#66FF66\">"+dza.getValue().getAvailable()+"</td>");
    		buffer.append("<td bgcolor=\"#FF4833\">"+dza.getValue().getInuse()+"</td>" );
    		buffer.append("<td>"+dza.getValue().getTotal()+"</td>" );

    		buffer.append("</tr>");
        }

        buffer.append("</table></body></html>");
    	return buffer.toString();
    }

    private static String headersString(final HttpServletRequest request)
    {
        final Map<String, List<String>> headerMap = new TreeMap<String, List<String>>();

        final Enumeration<String> headerNames = request.getHeaderNames();
        while (headerNames.hasMoreElements())
        {
            final List<String> headerValueList = new ArrayList<String>();

            final String headerName = headerNames.nextElement();

            final Enumeration<String> headerValues = request.getHeaders(headerName);
            while (headerValues.hasMoreElements())
            {
                headerValueList.add(headerValues.nextElement());
            }

            headerMap.put(headerName,
                          headerValueList);
        }

        return headerMap.toString();
    }



    privatew static void validateAuthorization(final HttpServletRequest request)
            throws JSONException
    {
        final String authorization = request.getHeader("authorization");

        if (authorization != null)
        {
            if (authorization.startsWith("Basic "))
            {
                final String basicAuthEncoded = authorization.substring(6);

                final byte[] basicAuthDecoded = DatatypeConverter.parseBase64Binary(basicAuthEncoded);

                final String[] split = new String(basicAuthDecoded).split(":");

                if (split.length == 2)
                {
                    if ((AUTHENTICATION_USER.equals(split[0])) &&
                        (AUTHENTICATION_PASSWORD.equals(split[1])))
                    {
                        return;
                    }
                }
            }
        }

        throw new WebApplicationException(createJSONResponse(Status.UNAUTHORIZED,
                                                             "WWW-Authenticate",
                                                             "Basic realm=\"Restricted Area\"",
                                                             "Not authorized"));
    }

	private static Response createJSONResponse(final Status status,
			final String text) throws JSONException {
		LOGGER.severe("Response status: " + status.getStatusCode() + ", text: "
				+ text);

		final JSONObject jsonObject = new JSONObject();
		jsonObject.put("description", text);

		return Response.status(status).type(MediaType.APPLICATION_JSON)
				.entity(jsonObject).build();
	}

	private static Response createJSONResponse(final Status status,
			final JSONObject jsonObject) throws JSONException {
		LOGGER.severe("Response status: " + status.getStatusCode() + ", body: "
				+ jsonObject.toString());

		return Response.status(status).type(MediaType.APPLICATION_JSON)
				.entity(jsonObject).build();
	}

	private static Response createJSONResponse(final Status status,
			final String header, final String headerValue, final String text)
			throws JSONException {
		final JSONObject jsonObject = new JSONObject();
		jsonObject.put("description", text);

		return Response.status(status).header(header, headerValue)
				.type(MediaType.APPLICATION_JSON).entity(jsonObject).build();
	}


    @SuppressWarnings("unchecked")
    private static <T> T getInput(final JSONObject jsonObject,
                                   final String     name,
                                   final Class<T>   inputClass)
            throws JSONException
    {
        final Object input = jsonObject.opt(name);

        if (input == null)
        {
            throw new WebApplicationException(createJSONResponse(Status.BAD_REQUEST,
                                                                 name + " not found in JSON payload"));
        }

        if (!(inputClass.isInstance(input)))
        {
            throw new WebApplicationException(createJSONResponse(Status.BAD_REQUEST,
                                                                 name + " must be of type " + inputClass.getName()));
        }

        return (T) input;
    }

    private static boolean getInputBoolean(final JSONObject jsonObject,
                                           final String     name)
            throws JSONException
    {
        return getInput(jsonObject,
                        name,
                        Boolean.class).booleanValue();
    }

    private static String getInputString(final JSONObject jsonObject,
                                         final String     name)
            throws JSONException
    {
        final String string = getInput(jsonObject,
                                       name,
                                       String.class);

//        if (string.trim().isEmpty())
//        {
//            throw new WebApplicationException(createJSONResponse(Status.BAD_REQUEST,
//                                                                 name + " cannot be empty"));
//        }

        return string;
    }

	private static String getOptionalInputString(final JSONObject jsonObject,
			final String name) throws JSONException {

		final String string = (String) jsonObject.opt(name);
		return string;
	}


	private static Long getInputLong(final JSONObject jsonObject,
			final String name) throws JSONException {
		return  getInput(jsonObject, name, Long.class);

	}


}
