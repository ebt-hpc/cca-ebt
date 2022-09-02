FROM codinuum/cca:devel-20.04

MAINTAINER ebtxhpc

RUN set -x && \
    mkdir -p /var/lib/cca/log && \
    mkdir -p /var/lib/cca/projects && \
    mkdir -p /var/lib/cca/mongo/db && \
    mkdir -p /mnt/mongo && \
    chown -R cca:cca /var/lib/cca && \
    chmod -R a+w /var/lib/cca

COPY cca /opt/cca/

RUN set -x && \
    apt-get update && \
    env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
            gnupg2 && \
    wget -qO - https://www.mongodb.org/static/pgp/server-6.0.asc | apt-key add - && \
    echo "deb [ arch=amd64,arm64 ] https://repo.mongodb.org/apt/ubuntu focal/mongodb-org/6.0 multiverse" \
            | tee /etc/apt/sources.list.d/mongodb-org-6.0.list && \
    apt-get update && \
    env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
            mongodb-org

RUN set -x && \
    apt-get update && \
    env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
            python3-psutil \
            python3-requests \
            python3-pymongo \
            apache2 \
            bindfs && \
    pip3 install msgpack simplejson scipy scikit-learn sympy gensim supervisor

COPY python /root/python

RUN set -x && \
    cd /root/python && \
    python3 -m build && \
    pip3 install dist/ebt-*.tar.gz && \
    cd /root && \
    rm -r python

COPY supervisord.conf /etc/
COPY supervisord-linux.conf /etc/
COPY --chown=www-data:www-data www /var/www/
COPY apache2/sites-available/*.conf /etc/apache2/sites-available/
COPY apache2/conf-available/*.conf /etc/apache2/conf-available/

RUN set -x && \
    a2ensite cca cca-ssl && \
    a2dissite 000-default && \
    a2enconf serve-cgi-bin && \
    a2enmod cgid && \
    mkdir /var/run/apache2 && \
    cd /var/www/outline/treeview && \
    mkdir metrics outline target topic && \
    wget https://code.jquery.com/jquery-3.6.1.min.js && \
    wget https://jqueryui.com/resources/download/jquery-ui-1.13.2.zip && \
    wget https://codemirror.net/5/codemirror.zip && \
    git clone https://github.com/vakata/jstree && \
    unzip jquery-ui-1.13.2.zip && \
    unzip codemirror.zip && \
    rm jquery-ui-1.13.2.zip && \
    rm codemirror.zip && \
    chown www-data:www-data jquery-3.6.1.min.js && \
    chown -R www-data:www-data jquery-ui-1.13.2 && \
    chown -R www-data:www-data jstree metrics outline target topic && \
    ln -s jquery-3.6.1.min.js jquery.min.js && \
    ln -s jquery-ui-1.13.2 jquery-ui && \
    ln -s codemirror-* codemirror && \
    ln -s /var/lib/cca/projects .

RUN set -x && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

CMD ["/bin/bash"]
