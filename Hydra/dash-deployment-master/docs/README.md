## Docs
You should now populate your master file ./source/index.rst and create other documentation
source files. Use the Makefile to build the docs, like so:
   make builder
where "builder" is one of the supported builders, e.g. html, latex or linkcheck.

### Docs are build in their own root directory

```
├── dash-deployment/
│   ├── README.md
│   ├── deploy.sh
│   ├── terminate_aws_instances.py
│   ├── delete_ucd_application_property.py
│   ├── portables.py
│   ├── procure_aws_guardium.py
│   ├── procure_aws_mpp.py
│   ├── quick-test.py
│   ├── setup_deployment_environment.py
│   ├── adddnsrecord.py
│   ├── aws/
│   │   ├── README.md
│   │   ├── __init__.py
│   │   ├── provision.py
│   │   ├── keys/
│   │   └── templates/
│   ├── common/
│   │   ├── __init__.py
│   │   └── util.py
│   ├── docs/
│   │   ├── make.bat
│   │   ├── Makefile
│   │   ├── README.md
│   │   ├── source
│   │   └── work
│   ├── sl/
│   │   ├── __init__.py
│   │   ├── cli.py
│   │   ├── loadfromimage.py
│   │   ├── slapi.py
│   │   └── wait_hw.py
│   ├── ucd/
│   │   ├── __init__.py
│   │   ├── cli.py
│   │   ├── udclient.zip
│   │   ├── jsonTemplates/
│   │   └── work/
│   ├── cloudant/
│   ├── logs/
│   └── work/
└── dash-deployment-docs/
    ├── doctrees/           <-- this directory is autogenerated, but not committed to gh-pages
    └── html/               <-- everything *under* here is committed to the gh-pages branch
        ├── index.html
        ├── (more generated html stuffs)
        ├── _modules/
        ├── _sources/
        └── _static/
```

## Style
We're following Google's [python style guide](http://www.sphinx-doc.org/en/stable/ext/example_google.html) on docstrings

## Building
1. cd docs
2. make html
3. cd ../../dash-deployment-docs/html
4. git brach  # Confirm you're on gh-pages
5. git add -A
6. git commit -m "Publishing updated docs..."
7. git push origin gh-pages
