FROM continuumio/anaconda3:latest

RUN set -x \
        && apt-get update -y \
        && pip install --upgrade pip \
        && pip install mglearn \
	    && pip uninstall urllib3 -y \
		&& pip uninstall  chardet -y && pip install requests \
		&& conda install jupyter -y --quiet

EXPOSE 8888

WORKDIR /data/jupyter

COPY ./scripts /data/scripts

RUN chmod +x /data/scripts/*.sh

CMD [ "/data/scripts/entrypoint.sh" ]




#CMD ["jupyter", "notebook", "--ip=0.0.0.0", "--no-browser", "--allow-root"]
