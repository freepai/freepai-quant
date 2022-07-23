#!/bin/bash
#export CONDA_EXE='/opt/conda/bin/conda'
#export CONDA_PYTHON_EXE='opt/conda/bin/python'
#
#echo setting conda cache
#$CONDA_EXE config --remove pkgs_dirs /opt/conda_pkgs_cache
#cp -n -r /opt/conda/pkgs/* /opt/conda_pkgs_cache/
#$CONDA_EXE clean --all -y
#$CONDA_EXE config --prepend pkgs_dirs /opt/conda_pkgs_cache
#
#echo update conda cache
#$CONDA_EXE update -n base conda -y
#$CONDA_EXE install jupyter -y
#$CONDA_EXE install -c conda-forge jupyter_contrib_nbextensions -y
#echo install conda packages
#$CONDA_EXE install $CONDA_PACKAGES -y
#
##pip --cache-dir /opt/pip_pkgs_cache
#echo install pip packages
##pip install $PIP_PACKAGES

apt-get install python3-mysql.connector -y
pip install mysql-connector-python

pip install runipy

echo "from notebook.auth import passwd
from os import environ
print(passwd(environ['NOTEBOOK_PASSWORD']))" > pwgen.py

export NOTEBOOK_PASSWORD_HASHED=$(python pwgen.py)

echo $NOTEBOOK_PASSWORD_HASHED
#export NOTEBOOK_PASSWORD_HASHED=sha1:ae96332532c9:700def4832276acc24fb39cb779216489229d7fa

#/usr/sbin/crond -f -c /etc/cron.d

if [ ! -f /root/.jupyter/jupyter_notebook_config.py ]; then
    /opt/conda/bin/jupyter notebook --generate-config
fi

/opt/conda/bin/jupyter notebook --notebook-dir=\'$NOTEBOOK_DIR\' --ip=\'$NOTEBOOK_IP\' --port=$NOTEBOOK_PORT --no-browser --allow-root --NotebookApp.password=\'$NOTEBOOK_PASSWORD_HASHED\'
cron

