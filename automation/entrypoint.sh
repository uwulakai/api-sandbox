#!/bin/sh
set -eu
# Fail before Jenkins starts if bootstrap credentials were not configured.
: "${JENKINS_ADMIN_USER:?Set JENKINS_ADMIN_USER}"
: "${JENKINS_ADMIN_PASSWORD:?Set JENKINS_ADMIN_PASSWORD}"
exec /usr/local/bin/jenkins.sh "$@"
