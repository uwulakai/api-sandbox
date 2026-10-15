FROM jenkins/jenkins:lts-jdk21

USER root
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-venv \
    && rm -rf /var/lib/apt/lists/*
RUN python3 -m venv /opt/test-venv
COPY e2e/requirements.txt /opt/e2e/requirements.txt
RUN /opt/test-venv/bin/pip install --no-cache-dir -r /opt/e2e/requirements.txt

USER jenkins
COPY automation/plugins.txt /usr/share/jenkins/ref/plugins.txt
RUN jenkins-plugin-cli --plugin-file /usr/share/jenkins/ref/plugins.txt
COPY automation/config.xml /usr/share/jenkins/ref/config.xml
COPY automation/init.groovy /usr/share/jenkins/ref/init.groovy.d/api-sandbox.groovy.override
COPY automation/Jenkinsfile /opt/automation/Jenkinsfile
COPY e2e/pytest.ini e2e/run.py /opt/e2e/
COPY e2e/tests /opt/e2e/tests
COPY --chmod=755 automation/entrypoint.sh /usr/local/bin/autotests-entrypoint.sh

ENV PATH="/opt/test-venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/autotests-entrypoint.sh"]
