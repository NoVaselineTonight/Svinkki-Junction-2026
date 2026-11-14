# Svinkki demo as a container. Standard library only: nothing is installed.
# The database is built during the image build from the organisers' public dataset (deploy/build_data.py).
# The dataset is not in this repository, and no key is ever in the image.

# ---- stage 1: fetch the dataset and build the demo database ---------------------------------------------
FROM python:3.13-slim AS data
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 SVINKKI_ENV_FILE=/tmp/no-env-file SVINKKI_AI_KEY_FILE=/tmp/no-key-file
WORKDIR /srv
# The download is its own step, so a rebuild after a code change reuses it instead of fetching 360 MB again.
COPY deploy/__init__.py deploy/build_data.py deploy/removed_customers.txt ./deploy/
RUN python -m deploy.build_data --fetch-only /srv/_dataset
COPY app ./app
# Random-login customers kept besides the six demo customers (0 = everyone, about 540 MB).
ARG SVINKKI_DEMO_POOL=300
RUN python -m deploy.build_data --source-dir /srv/_dataset --out /srv/data/svinkki.db --pool ${SVINKKI_DEMO_POOL}

# ---- stage 2: the app and the built database, nothing else -----------------------------------------------
FROM python:3.13-slim
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    SVINKKI_DB=/srv/data/svinkki.db \
    SVINKKI_STATE_DB=/tmp/svinkki/state.db \
    SVINKKI_AI_SETTINGS_FILE=/tmp/svinkki/ai_settings.json \
    SVINKKI_AI_KEY_FILE=/tmp/svinkki/no-key-file \
    SVINKKI_ENV_FILE=/tmp/svinkki/no-env-file \
    SVINKKI_PUBLIC=1 \
    PORT=10000
WORKDIR /srv
COPY app ./app
COPY web ./web
COPY deploy ./deploy
COPY --from=data /srv/data ./data

# Run as an ordinary user; the app only writes its demo state under /tmp/svinkki.
RUN useradd --system --home /srv svinkki && mkdir -p /tmp/svinkki && chown -R svinkki /tmp/svinkki
USER svinkki

EXPOSE 10000
CMD ["python", "-m", "deploy.serve"]
