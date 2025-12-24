FROM qgis/qgis:release-3_16

USER root

ENV QT_QPA_PLATFORM=offscreen
ENV QGIS_PREFIX_PATH=/usr
ENV QGIS_DEBUG=0
ENV QGIS_LOG_FILE=/tmp/qgis.log
ENV XDG_RUNTIME_DIR=/tmp/runtime-root

RUN mkdir -p /tmp/runtime-root && chmod -R 777 /tmp/runtime-root

RUN apt-get update && \
    apt-get install -y python3-psycopg2 && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /scripts

COPY console_listener_without_user_logic.py /scripts/
COPY test_algorithm_project_3_16.qgz /scripts/
COPY Найкоротший_маршрут_бордюри_з_стилями_2.model3 /scripts/
