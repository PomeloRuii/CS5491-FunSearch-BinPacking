ARG NUMPY_IMAGE
ARG PYTHON_IMAGE
FROM ${NUMPY_IMAGE} AS installed
FROM ${PYTHON_IMAGE}
# Copy only installed numerical dependencies, never the legacy /app data/layers.
COPY --from=installed /usr/local/lib/python3.10/site-packages/numpy /usr/local/lib/python3.10/site-packages/numpy
COPY --from=installed /usr/local/lib/python3.10/site-packages/numpy.libs /usr/local/lib/python3.10/site-packages/numpy.libs
COPY --from=installed /usr/local/lib/python3.10/site-packages/numpy-1.26.4.dist-info /usr/local/lib/python3.10/site-packages/numpy-1.26.4.dist-info
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 HOME=/nonexistent
WORKDIR /app
COPY --chown=0:0 worker.py candidate_worker.py phase1d_worker.py research_core.py static_policy.py interface.py common.py specification.txt LICENSE research_data.json states.json dataset_scope.json development_or3.json /app/
RUN chmod 0555 /app && chmod 0444 /app/*
USER 65532:65532
WORKDIR /tmp
ENTRYPOINT ["python", "-I", "/app/worker.py"]
