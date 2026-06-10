# Stage 1: Build stage environment using alpine python Image
FROM alpine:3.23 AS build-env

# Set build directory
WORKDIR /build

# Copy only what's needed for the build
COPY requirements.txt .
COPY app/ ./app/

# Build Python 3.15.0a6 and apk dependencies from source
RUN set -e; \
    apk add --no-cache \
    build-base=0.5-r3 \
    libffi-dev=3.5.2-r0 \
    openssl-dev=3.5.7-r0 \
    zlib-dev=1.3.2-r0 \
    bzip2-dev=1.0.8-r6 \
    xz-dev=5.8.3-r0 \
    wget=1.25.0-r2; \
    wget --progress=dot:giga https://www.python.org/ftp/python/3.15.0/Python-3.15.0a6.tgz; \
    tar -xzf Python-3.15.0a6.tgz; \
    ./Python-3.15.0a6/configure --prefix=/usr/local --enable-shared --with-ensurepip=install; \
    make -j"$(nproc)"; \
    make install; \
    ln -s /usr/local/bin/python3.15 /usr/local/bin/python;

# Install python dependencies into a target directory, then remove pip so it
# is not present in the runtime image (avoids shipping pip CVEs at runtime)
RUN set -e; \
    pip3.15 install --no-cache-dir --upgrade 'pip==26.0'; \
    PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1 pip3.15 install --no-cache-dir -r requirements.txt --target /packages; \
    pip3.15 uninstall -y pip setuptools wheel 2>/dev/null || true; \
    find /usr/local/lib/python3.15 -type d -name 'pip*' -exec rm -rf {} + 2>/dev/null || true; \
    find /usr/local/lib/python3.15 -type d -name 'setuptools*' -exec rm -rf {} + 2>/dev/null || true;


# Stage 2: Runtime Stage using scratch Image
FROM scratch

# Copy necessary system libraries and interpreter from build-env
COPY --from=build-env /lib/ld-musl-x86_64.so.1 /lib/ld-musl-x86_64.so.1
COPY --from=build-env /lib/libc.musl-x86_64.so.1 /lib/libc.musl-x86_64.so.1
COPY --from=build-env /usr/local/lib/libpython3.15.so.1.0 /usr/local/lib/libpython3.15.so.1.0
COPY --from=build-env /usr/local/lib/python3.15 /usr/local/lib/python3.15
COPY --from=build-env /usr/lib/libssl.so.3 /usr/lib/libssl.so.3
COPY --from=build-env /usr/lib/libcrypto.so.3 /usr/lib/libcrypto.so.3
COPY --from=build-env /usr/lib/libz.so.1 /usr/lib/libz.so.1
COPY --from=build-env /usr/lib/libgcc_s.so.1 /usr/lib/libgcc_s.so.1
COPY --from=build-env /usr/lib/libffi.so.8 /usr/lib/libffi.so.8

# Copy Python binary
COPY --from=build-env /usr/local/bin/python /usr/local/bin/python

# Copy CA certificates needed for SSL verification
COPY --from=build-env /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/ca-certificates.crt

# Copy installed packages and application code
COPY --from=build-env /packages /packages
COPY --from=build-env /build/app /app

# Set required environment variables for Python
ENV PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=UTF-8 \
    PYTHONPATH=/packages \
    SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt \
    TMPDIR=/tmp \
    HOME=/tmp

# Set runtime directory
WORKDIR /app

# Expose the application port
EXPOSE 80

# Set up container healthcheck
HEALTHCHECK --interval=30s --timeout=3s --start-period=30s --retries=3 \
    CMD ["/usr/local/bin/python", "healthcheck/healthcheck.py"]

# Switch to non-privileged user
USER 1001:1001

# Define the command to run the application
CMD ["/usr/local/bin/python", "gunicorn_cfg.py"]
