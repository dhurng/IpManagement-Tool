# PortableIPMonitor


Building instructions
-----------------------------
1.  Clone the project.
2.  Run build.xml to build the project.  

This will generate the PortableIPMonitor.war file  in  <clone_location>/install/  folder. 

Now the app is ready for deployment on Bluemix.

Pushing to Bluemix
----------------------------
1.  For pushing to Bluemix , we need a manifest file .  A sample manifest file is provided in  <clone_location>/install  folder.
Push the app using the command.

cf push -f manifest.yml
