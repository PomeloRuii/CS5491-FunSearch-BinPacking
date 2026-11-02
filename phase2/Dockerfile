ARG BASE_IMAGE
FROM ${BASE_IMAGE}
USER 0:0
COPY --chown=0:0 phase1d_worker.py /app/phase1d_worker.py
COPY --chown=0:0 research_worker.py /app/candidate_worker.py
COPY --chown=0:0 research_data.json /app/research_data.json
COPY --chown=0:0 states.json /app/states.json
RUN chmod 0444 /app/phase1d_worker.py /app/candidate_worker.py /app/research_data.json /app/states.json
USER 65532:65532
