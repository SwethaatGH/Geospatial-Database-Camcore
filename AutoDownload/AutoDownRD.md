## Download Astro - managed airflow on a python 3.11 venv - **VERY IMPORTANT**
`winget install -e --id Astronomer.Astro
`
---
## Initialize astro project to get airflow set up
`astro dev init
`
---
## Update the requirements and packages.txt
requirements:
`pandas
psycopg2-binary
earthengine-api`
packages:
`gdal-bin`

---

## Make dirs in include folder (check if code auto does it )
---
## Update the Dockerfile to allow install of

`# Ensure we're running as root for apt operations
USER root
RUN apt-get update && \
    apt-get install -y software-properties-common gnupg2 && \
    apt-get update && \
    apt-get install -y postgresql-client postgis`
---
## Stop PostgreSQL to allow astro airflow to build and prevent port conflict
---
## Find your port number from cmd thro ip4 on ethernet or lan
`ipconfig`
---
## Modify .env to have the sql db connection and use the port number from the cmd
`AIRFLOW_CONN_POSTGRES_DEFAULT=postgresql://postgres:postgres@first3parts.sth:5432/dbname
`
---
## Modify `C:\Program Files\PostgreSQL\Version\data\pg_hba.conf` to add the below line to it
`host    all             all             first3parts.0/24            trust
`
---
## Create dag in dags folder as needed
---
## Start Astro
`astro dev start 
`
---
## Authenticate earthengine manually
`astro dev bash 
``earthengine authenticate --auth_mode=notebook
`
---
## Go to UI at localhost:8080 and run the pipeline

