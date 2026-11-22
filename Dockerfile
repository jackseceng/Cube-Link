# Stage 1: Build stage using the official Python 3.15 slim image (Debian/glibc).
# Using a glibc base means pyturso installs from a pre-built manylinux wheel
# rather than compiling from Rust source, which avoids musl build failures and
# cuts build time significantly.
FROM python:3.15-slim AS build-env

# Upgrade all system packages to pick up patched libgcc-s1 and Python libs
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*

# Set build directory
WORKDIR /build

# Copy only what's needed for the build
COPY requirements.txt .
COPY app/ ./app/

# Install python dependencies into a target directory, then remove pip so it
# is not present in the runtime image (avoids shipping pip CVEs at runtime)
RUN set -e; \
    pip install --no-cache-dir --upgrade 'pip==26.0'; \
    pip install --no-cache-dir -r requirements.txt --target /packages; \
    pip uninstall -y pip setuptools wheel 2>/dev/null || true; \
    find /usr/local/lib/python3.15 -type d -name 'pip*' -exec rm -rf {} + 2>/dev/null || true; \
    find /usr/local/lib/python3.15 -type d -name 'setuptools*' -exec rm -rf {} + 2>/dev/null || true;


# Stage 2: Runtime Stage using scratch Image
FROM scratch

# Copy necessary system libraries and interpreter from build-env.
# This list is derived by loading all app imports in python:3.15-slim and
# recording every .so that appears in /proc/self/maps.
#
# Linker — must live at the path the ELF interpreter field requests
COPY --from=build-env /usr/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2 /lib64/ld-linux-x86-64.so.2
# glibc
COPY --from=build-env /usr/lib/x86_64-linux-gnu/libc.so.6 /usr/lib/x86_64-linux-gnu/libc.so.6
COPY --from=build-env /usr/lib/x86_64-linux-gnu/libdl.so.2 /usr/lib/x86_64-linux-gnu/libdl.so.2
COPY --from=build-env /usr/lib/x86_64-linux-gnu/libm.so.6 /usr/lib/x86_64-linux-gnu/libm.so.6
COPY --from=build-env /usr/lib/x86_64-linux-gnu/libpthread.so.0 /usr/lib/x86_64-linux-gnu/libpthread.so.0
COPY --from=build-env /usr/lib/x86_64-linux-gnu/librt.so.1 /usr/lib/x86_64-linux-gnu/librt.so.1
# Python runtime
COPY --from=build-env /usr/local/lib/libpython3.15.so.1.0 /usr/local/lib/libpython3.15.so.1.0
COPY --from=build-env /usr/local/lib/python3.15 /usr/local/lib/python3.15
# OpenSSL (required by ssl, hashlib, cryptography)
COPY --from=build-env /usr/lib/x86_64-linux-gnu/libssl.so.3 /usr/lib/x86_64-linux-gnu/libssl.so.3
COPY --from=build-env /usr/lib/x86_64-linux-gnu/libcrypto.so.3 /usr/lib/x86_64-linux-gnu/libcrypto.so.3
# Compression libs (required by zlib, bz2, lzma, zstd modules)
COPY --from=build-env /usr/lib/x86_64-linux-gnu/libz.so.1 /usr/lib/x86_64-linux-gnu/libz.so.1
COPY --from=build-env /usr/lib/x86_64-linux-gnu/libzstd.so.1 /usr/lib/x86_64-linux-gnu/libzstd.so.1
COPY --from=build-env /usr/lib/x86_64-linux-gnu/libbz2.so.1.0 /usr/lib/x86_64-linux-gnu/libbz2.so.1.0
COPY --from=build-env /usr/lib/x86_64-linux-gnu/liblzma.so.5 /usr/lib/x86_64-linux-gnu/liblzma.so.5
# Other Python built-in module deps
COPY --from=build-env /usr/lib/x86_64-linux-gnu/libmpdec.so.4 /usr/lib/x86_64-linux-gnu/libmpdec.so.4
COPY --from=build-env /usr/lib/x86_64-linux-gnu/libuuid.so.1 /usr/lib/x86_64-linux-gnu/libuuid.so.1
COPY --from=build-env /usr/lib/x86_64-linux-gnu/libffi.so.8 /usr/lib/x86_64-linux-gnu/libffi.so.8
COPY --from=build-env /usr/lib/x86_64-linux-gnu/libgcc_s.so.1 /usr/lib/x86_64-linux-gnu/libgcc_s.so.1

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
