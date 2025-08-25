FROM astrocrpublic.azurecr.io/runtime:3.0-1
# Ensure we're running as root for apt operations
USER root
# Install GDAL dependencies
RUN apt-get update && \
    apt-get install -y software-properties-common gnupg2 && \
    apt-get update && \
    apt-get install -y postgresql-client postgis
