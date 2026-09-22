ARG BUILD_FROM
FROM ${BUILD_FROM}

ARG BUILD_ARCH
ARG BUILD_VERSION

LABEL \
	io.hass.name="Energy Ledger" \
	io.hass.description="Virtual prosumer storage and TAURON G13 live cost" \
	io.hass.arch="${BUILD_ARCH}" \
	io.hass.type="app" \
	io.hass.version="${BUILD_VERSION}"

ENV LANG=C.UTF-8
ENV PATH="/opt/venv/bin:${PATH}"

WORKDIR /usr/src/app

COPY rootfs/requirements.txt /tmp/requirements.txt
RUN apk add --no-cache python3 py3-pip tzdata \
	&& apk add --no-cache --virtual .build-deps gcc musl-dev python3-dev libffi-dev \
	&& python3 -m venv /opt/venv \
	&& /opt/venv/bin/pip install --no-cache-dir -r /tmp/requirements.txt \
	&& apk del .build-deps

COPY rootfs/usr/src/app/energy_ledger /usr/src/app/energy_ledger
COPY run.sh /run.sh

RUN chmod a+x /run.sh

CMD ["/run.sh"]
